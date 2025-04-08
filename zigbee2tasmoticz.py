try:
    import collections.abc as collections
except ImportError:  # Python <= 3.2 including Python 2
    import collections

errmsg = ""
try:
    import Domoticz
except Exception as e:
    errmsg += "Domoticz core start error: "+str(e)
#try:
#    import json
#except Exception as e:
#    errmsg += " Json import error: "+str(e)
#try:
#    import binascii
#except Exception as e:
#    errmsg += " binascii import error: "+str(e)
try:
    import time
    from datetime import datetime, timedelta
except Exception as e:
    errmsg += " datetime import error: "+str(e)


tasmotaDebug = True


# Decide if tasmota.py debug messages should be displayed if domoticz debug is enabled for this plugin
def setTasmotaDebug(flag):
    global tasmotaDebug
    tasmotaDebug = flag


# Replaces Domoticz.Debug() so tasmota related messages can be turned off from plugin.py
def Debug(msg):
    if tasmotaDebug:
        Domoticz.Debug(msg)


# Handles incoming Tasmota messages from MQTT or Domoticz commands for Tasmota devices
class Handler:
    def __init__(self, prefix1, prefix2, mqttClient, devices):
        Debug("Handler::__init__(cmnd: {}, tele: {})".format(
            prefix1, prefix2))

        if errmsg != "":
            Domoticz.Error(
                "Handler::__init__: Domoticz Python env error {}".format(errmsg))

        # So far only STATUS, STATE, SENSOR and RESULT are used. Others just for research...
#        self.topics = ['INFO1', 'STATE', 'SENSOR', 'RESULT', 'STATUS',
#                       'STATUS5', 'STATUS8', 'STATUS11', 'ENERGY']

        self.prefix = [None, prefix1, prefix2]
#        self.subscriptions = subscriptions
        self.mqttClient = mqttClient

        # I don't understand variable (in)visibility
        global Devices
        Devices = devices

    def debug(self, flag):
        global tasmotaDebug
        tasmotaDebug = flag

    # Translate domoticz command to tasmota mqtt command(s?)
    def onDomoticzCommand(self, Unit, Command, Level, Color):
        Debug("Handler::onDomoticzCommand: Unit: {}, Command: {}, Level: {}, Color: {}".format(
            Unit, Command, Level, Color))
        if Devices[Unit].Type == 244:
            Debug("Switchtype {}".format(Devices[Unit].SwitchType))
            if Command == "On" or Command == "Off": #Devices[Unit].SwitchType == 0:
#                cmdnum= "1" if Command == "On" else "0"
                payload="{ \"Device\":"+Devices[Unit].DeviceID+", \"Send\":{\"Power\":\""+Command+"\"} }"
                topic = self.prefix[1]+"/ZbSend"
                Domoticz.Log("Send Command {} to {}".format(Command,Devices[Unit].Name))
                Debug("Publish topic {} payload {}".format(topic,payload))
                self.mqttClient.publish(topic, payload)
            elif Command == "Set Level":
                payload="{ \"Device\":"+Devices[Unit].DeviceID+", \"Send\":{\"Dimmer\":"+str(int(Level*2.55))+"} }"
                topic = self.prefix[1]+"/ZbSend"
                Domoticz.Log("Send Command {} {} to {}".format(Command, str(int(Level*2.55)),Devices[Unit].Name))
                Debug("Publish topic {} payload {}".format(topic,payload))
                self.mqttClient.publish(topic, payload)
                if Level > 0 and Devices[Unit].nValue == 0: #we need to switch it on if it was off
                    payload="{ \"device\":"+Devices[Unit].DeviceID+", \"send\":{\"Power\":1} }"
                    self.mqttClient.publish(topic, payload)
        return True

    # Subscribe to our topics
    def onMQTTConnected(self):
        subs = []
        subs.append(self.prefix[2])
        Debug('Handler::onMQTTConnected: Subscriptions: {}'.format(repr(subs)))
        self.mqttClient.subscribe(subs)

    # Process incoming MQTT messages from Tasmota devices
    def onMQTTPublish(self, topic, message):
        Debug("Handler::onMQTTPublish: topic: {}, message {}".format(topic,message))
        if 'ZbReceived' in message:
            keys=list(message['ZbReceived'].keys())
            for key in keys:
                if 'Name' in message['ZbReceived'][key]:
                    friendlyname = message['ZbReceived'][key]['Name']
                else:
                    friendlyname = message['ZbReceived'][key]['Device']
                if 'Endpoint' in message['ZbReceived'][key] and message['ZbReceived'][key]['Endpoint'] > 1:
                    device = message['ZbReceived'][key]['Device']+'-'+str(message['ZbReceived'][key]['Endpoint'])
                else:
                    device = message['ZbReceived'][key]['Device']
                if 'Temperature' in message['ZbReceived'][key]:
                    updateTemp(device,message['ZbReceived'][key]['Temperature'], friendlyname)
                if 'Humidity' in message['ZbReceived'][key]:
                    updateHumidity(device, message['ZbReceived'][key]['Humidity'], friendlyname)
                if 'BatteryPercentage' in message['ZbReceived'][key]:
                    updateBatteryPercentage(device, message['ZbReceived'][key]['BatteryPercentage'])
                if 'BatteryVoltage' in message['ZbReceived'][key]:
                    updateBatteryVoltage(device, message['ZbReceived'][key]['BatteryVoltage'])
                if 'LinkQuality' in message['ZbReceived'][key]:
                    updateLinkQuality(device, message['ZbReceived'][key]['LinkQuality'])
                if 'Power' in message['ZbReceived'][key]:
                    updateSwitch(device, message['ZbReceived'][key]['Power'], friendlyname)
                if 'Dimmer' in message['ZbReceived'][key]:
                    updateDimmer(device, message['ZbReceived'][key]['Dimmer'], friendlyname)
                if 'Water' in message['ZbReceived'][key]:
                    updateSwitch(device, message['ZbReceived'][key]['Water'], friendlyname)
                if 'Occupancy' in message['ZbReceived'][key]:
                    updateSwitch(device, message['ZbReceived'][key]['Occupancy'], friendlyname)
                if 'Illuminance' in message['ZbReceived'][key]:
                    updateLightsensor(device, message['ZbReceived'][key]['Illuminance'], friendlyname)

    def checkTimeoutDevices(self, timeout):
        for idx in Devices:
            now = datetime.now()
            last = datetime.fromtimestamp(time.mktime(time.strptime(Devices[idx].LastUpdate, "%Y-%m-%d %H:%M:%S")))
            delta = timedelta(minutes=int(timeout))
            if now - last > delta:
                if Devices[idx].Type != 244:
                    Devices[idx].Update(nValue = Devices[idx].nValue, sValue = Devices[idx].sValue, TimedOut=1)

###########################
# Tasmota Utility functions


def updateTemp(shortaddr,temperature,friendlyname):
    create=True
    for idx in Devices:
        if Devices[idx].DeviceID == shortaddr:
           if Devices[idx].Type == 80: #Temperature
              Devices[idx].Update(nValue=0, sValue="{:.1f}".format(temperature), TimedOut=0)
              Domoticz.Log("Update Device {} Temperature {}".format(Devices[idx].Name,temperature))
           elif Devices[idx].Type == 81: #Humidity
              Devices[idx].Update(TypeName="Temp+Hum",nValue=0, sValue="{:.1f};{};{}".format(temperature,Devices[idx].nValue,Devices[idx].sValue), TimedOut=0)
              Domoticz.Log("Update Device {} to Temp+Hum Temperature {}".format(Devices[idx].Name,temperature))
           elif Devices[idx].Type == 82: #Temp+Hum
              svalue=Devices[idx].sValue
              parts=svalue.split(';')
              parts[0]="{:.1f}".format(temperature)
              svalue=";".join(parts)
              Devices[idx].Update(nValue=0, sValue=svalue, TimedOut=0)
              Domoticz.Log("Update Device {} Temperature {}".format(Devices[idx].Name,temperature))
           create=False
    if create:
        createDevice(deviceid=shortaddr,devicetype="Temperature",name=friendlyname,nvalue=0,svalue="{:.1f}".format(temperature))


def updateHumidity(shortaddr, humidity,friendlyname):
    create=True
    if humidity<40:
        humstat="2"
    elif humidity>60:
        humstat="3"
    else:
        humstat="1"
    for idx in Devices:
        if Devices[idx].DeviceID == shortaddr:
           if Devices[idx].Type == 81: #Humidity
              Devices[idx].Update(nValue=int(round(humidity)), sValue=humstat, TimedOut=0)
              Domoticz.Log("Update Device {} Humidity {}".format(Devices[idx].Name,humidity))
           elif Devices[idx].Type == 80: #Temperature
              Devices[idx].Update(TypeName="Temp+Hum",nValue=0, sValue="{};{};{}".format(Devices[idx].sValue,int(round(humidity)),humstat), TimedOut=0)
              Domoticz.Log("Update Device {} to Temp+Hum Humidity {}".format(Devices[idx].Name,humidity))
           elif Devices[idx].Type == 82: #Temp+Hum
              svalue=Devices[idx].sValue
              parts=svalue.split(';')
              parts[1]=str(int(round(humidity)))
              parts[2]=humstat
              svalue=";".join(parts)
              Devices[idx].Update(nValue=0, sValue=svalue, TimedOut=0)
              Domoticz.Log("Update Device {} Humidity {}".format(Devices[idx].Name,humidity))
           create=False
    if create:
        createDevice(deviceid=shortaddr,devicetype="Humidity",name=friendlyname,nvalue=int(round(humidity)),svalue=humstat)

def updateLightsensor(shortaddr, illuminance, friendlyname):
    create = True
    lux = round(10**(illuminance/10000)-1) # according to zigbee documentation
    for idx in Devices:
        if Devices[idx].DeviceID == shortaddr:
           if Devices[idx].Type == 246: # Lux
              Devices[idx].Update(nValue=0,sValue=str(lux), TimedOut=0)
              Domoticz.Log("Update Device {} Lux {}".format(Devices[idx].Name,lux))
           create=False
    if create:
        createDevice(deviceid=shortaddr,devicetype="Illumination",name=friendlyname,nvalue=0,svalue=str(lux))

def updateBatteryPercentage(shortaddr, battery_percentage):
    for idx in Devices:
        if Devices[idx].DeviceID == shortaddr:
           Devices[idx].Update(nValue=Devices[idx].nValue, sValue=Devices[idx].sValue, BatteryLevel=int(battery_percentage))
           Debug("Update Device {} Battery Percentage: {}".format(Devices[idx].Name, battery_percentage))

def updateBatteryVoltage(shortaddr, battery_voltage): #do nothing
    Debug("Device: {}, Battery Voltage: {}".format(shortaddr, battery_voltage))

def updateLinkQuality(shortaddr, link_quality):
    for idx in Devices:
        if Devices[idx].DeviceID == shortaddr:
           Devices[idx].Update(nValue=Devices[idx].nValue, sValue=Devices[idx].sValue, SignalLevel=int(min(round(link_quality/254*12),12)))
           Debug("Device: {}, Link Quality: {}".format(Devices[idx].Name, link_quality))

def updateSwitch(shortaddr, power, friendlyname):
    Debug("Device: {}, Power: {}".format(shortaddr, power))
    create=True
    for idx in Devices:
        if Devices[idx].DeviceID == shortaddr:
           if Devices[idx].Type == 244:
               if Devices[idx].SwitchType == 7:
                   Devices[idx].Update(nValue=power,sValue= Devices[idx].sValue)
               else:
                   Devices[idx].Update(nValue=power,sValue="On" if power == 1 else "Off")
               Domoticz.Log("Update switch {} nvalue {} svalue {}".format(friendlyname,power,"On" if power == 1 else "Off"))
           create=False
    if create:
        createDevice(deviceid=shortaddr,devicetype="Switch",name=friendlyname,nvalue=power,svalue="")

def updateDimmer(shortaddr, dimmer, friendlyname): #dimmers are not created but only updated from existing switches
    Debug("Device: {}, Dimmer: {}".format(shortaddr, dimmer))
    for idx in Devices:
        if Devices[idx].DeviceID == shortaddr:
#           Debug("SwitchType {}".format(Devices[idx].SwitchType))
           if Devices[idx].Type == 244:
               if Devices[idx].SwitchType !=7:
                   Devices[idx].Update(Subtype=73,Switchtype=7,sValue=str(int(round(dimmer/2.55))),nValue=Devices[idx].nValue)
               Devices[idx].Update(sValue=str(int(round(dimmer/2.55))),nValue=Devices[idx].nValue)
#               Devices[idx].Update(nValue=power,sValue="On" if power == 1 else "Off")
               Domoticz.Log("Update dimmer {}  {}".format(friendlyname,dimmer))


def createDevice(deviceid, devicetype, name, nvalue, svalue):
    Domoticz.Log("Create Device: {} {}".format(name, devicetype))
    unit = findfreeUnit()
    Domoticz.Device(Name=name, Unit=unit, TypeName=devicetype, Used=1, DeviceID=deviceid).Create()
    if unit in Devices:
#        Devices[unit].Update(nValue=Devices[unit].nValue, sValue=Devices[unit].sValue, Name=name, SuppressTriggers=True)
        Devices[unit].Update(nValue=nvalue, sValue=svalue)
#    for idx in Devices:
#        if Devices[idx].DeviceID == deviceid:
#           Devices[idx].Update(nValue=nvalue, sValue=svalue)

def findfreeUnit():
    for idx in range(1, 512):
        if idx not in Devices:
            break
    return idx
