try:
    import collections.abc as collections
except ImportError:  # Python <= 3.2 including Python 2
    import collections

errmsg = ""
try:
    import Domoticz
except Exception as e:
    errmsg += "Domoticz core start error: "+str(e)
try:
    import json
except Exception as e:
    errmsg += " Json import error: "+str(e)
try:
    import binascii
except Exception as e:
    errmsg += " binascii import error: "+str(e)


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
        self.topics = ['INFO1', 'STATE', 'SENSOR', 'RESULT', 'STATUS',
                       'STATUS5', 'STATUS8', 'STATUS11', 'ENERGY']

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
                cmdnum= "1" if Command == "On" else "0"
                payload="{ \"device\":"+Devices[Unit].DeviceID+", \"send\":{\"Power\":"+cmdnum+"} }"
                topic = self.prefix[1]+"/ZbSend"
                Domoticz.Log("Send Command {} to {}".format(Command,Devices[Unit].Name))
                Debug("Publish topic {} payload {}".format(topic,payload))
                self.mqttClient.publish(topic, payload)
            elif Command == "Set Level":
                payload="{ \"device\":"+Devices[Unit].DeviceID+", \"send\":{\"Dimmer\":"+str(int(Level*2.55))+"} }"
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
                if 'Temperature' in message['ZbReceived'][key]:
                    updateTemp(message['ZbReceived'][key]['Device'],message['ZbReceived'][key]['Temperature'], message['ZbReceived'][key]['Name'])
                if 'Humidity' in message['ZbReceived'][key]:
                    updateHumidity(message['ZbReceived'][key]['Device'], message['ZbReceived'][key]['Humidity'], message['ZbReceived'][key]['Name'])
                if 'BatteryPercentage' in message['ZbReceived'][key]:
                    updateBatteryPercentage(message['ZbReceived'][key]['Device'], message['ZbReceived'][key]['BatteryPercentage'])
                if 'BatteryVoltage' in message['ZbReceived'][key]:
                    updateBatteryVoltage(message['ZbReceived'][key]['Device'], message['ZbReceived'][key]['BatteryVoltage'])
                if 'LinkQuality' in message['ZbReceived'][key]:
                    updateLinkQuality(message['ZbReceived'][key]['Device'], message['ZbReceived'][key]['LinkQuality'])
                if 'Power' in message['ZbReceived'][key]:
                    updateSwitch(message['ZbReceived'][key]['Device'], message['ZbReceived'][key]['Power'], message['ZbReceived'][key]['Name'])
                if 'Dimmer' in message['ZbReceived'][key]:
                    updateDimmer(message['ZbReceived'][key]['Device'], message['ZbReceived'][key]['Dimmer'], message['ZbReceived'][key]['Name'])

###########################
# Tasmota Utility functions


def updateTemp(shortaddr,temperature,friendlyname):
    create=True
    for Device in Devices:
        if Devices[Device].DeviceID == shortaddr:
           if Devices[Device].Type == 80: #Temperature
              Devices[Device].Update(nValue=0, sValue="{}".format(temperature))
              Domoticz.Log("Update Device {} Temperature {}".format(Devices[Device].Name,temperature))
           elif Devices[Device].Type == 81: #Humidity
              Devices[Device].Update(TypeName="Temp+Hum",nValue=0, sValue="{};{};1".format(temperature,Devices[Device].nValue))
              Domoticz.Log("Update Device {} to Temp+Hum Temperature {}".format(Devices[Device].Name,temperature))
           elif Devices[Device].Type == 82: #Temp+Hum
              svalue=Devices[Device].sValue
              parts=svalue.split(';')
              parts[0]=str(temperature)
              svalue=";".join(parts)
              Devices[Device].Update(TypeName="Temp+Hum",nValue=0, sValue=svalue)
              Domoticz.Log("Update Device {} Temperature {}".format(Devices[Device].Name,temperature))
           create=False
    if create or len(Devices)==0:
        createDevice(shortaddr,devicetype="Temperature",name=friendlyname,nvalue=0,svalue="{}".format(temperature))


def updateHumidity(shortaddr, humidity,friendlyname):
    create=True
    if humidity<40:
        humstat="2"
    elif humidity>60:
        humstat="3"
    else:
        humstat="1"
    for Device in Devices:
        if Devices[Device].DeviceID == shortaddr:
           if Devices[Device].Type == 81: #Humidity
#              Debug("Device {}".format(Devices[Device].Type))
              Devices[Device].Update(nValue=int(humidity), sValue=humstat)
              Domoticz.Log("Update Device {} Humidity {}".format(Devices[Device].Name,humidity))
           elif Devices[Device].Type == 80: #Temperature
#              Devices[Device].Update(TypeName="Temp+Hum")
              Devices[Device].Update(TypeName="Temp+Hum",nValue=0, sValue="{};{};{}".format(Devices[Device].sValue,humidity,humstat))
              Domoticz.Log("Update Device {} to Temp+Hum Humidity {}".format(Devices[Device].Name,humidity))
           elif Devices[Device].Type == 82: #Temp+Hum
              svalue=Devices[Device].sValue
              parts=svalue.split(';')
              parts[1]=str(humidity)
              parts[2]=humstat
              svalue=";".join(parts)
              Devices[Device].Update(TypeName="Temp+Hum",nValue=0, sValue=svalue)
              Domoticz.Log("Update Device {} Humidity {}".format(Devices[Device].Name,humidity))
#              Debug("type temp+hum update. svalue = {}".format(svalue))
           create=False
    if create or len(Devices)==0:
        createDevice(shortaddr,devicetype="Humidity",name=friendlyname,nvalue=humidity,svalue=humstat)

def updateBatteryPercentage(shortaddr, battery_percentage):
    for Device in Devices:
        if Devices[Device].DeviceID == shortaddr:
           Devices[Device].Update(nValue=Devices[Device].nValue, sValue=Devices[Device].sValue, BatteryLevel=int(battery_percentage))
           Debug("Update Device {} Battery Percentage: {}".format(Devices[Device].Name, battery_percentage))

def updateBatteryVoltage(shortaddr, battery_voltage): #do nothing
    Debug("Device: {}, Battery Voltage: {}".format(shortaddr, battery_voltage))

def updateLinkQuality(shortaddr, link_quality):
    for Device in Devices:
        if Devices[Device].DeviceID == shortaddr:
           Devices[Device].Update(nValue=Devices[Device].nValue, sValue=Devices[Device].sValue, SignalLevel=int(min(link_quality*.1,12)))
           Debug("Device: {}, Link Quality: {}".format(Devices[Device].Name, link_quality))

def updateSwitch(shortaddr, power, friendlyname):
    Debug("Device: {}, Power: {}".format(shortaddr, power))
    create=True
    for Device in Devices:
        if Devices[Device].DeviceID == shortaddr:
#           Debug("TypeID {}".format(Devices[Device].Type))
           if Devices[Device].Type == 244:
               if Devices[Device].SwitchType ==7:
                   Devices[Device].Update(nValue=power,sValue= Devices[Device].sValue)
               else:
                   Devices[Device].Update(nValue=power,sValue="On" if power == 1 else "Off")
               Domoticz.Log("Update switch {} nvalue {} svalue {}".format(friendlyname,power,"On" if power == 1 else "Off"))
           create=False
    if create or len(Devices)==0:
        createDevice(shortaddr,devicetype="Switch",name=friendlyname,nvalue=power,svalue="")

def updateDimmer(shortaddr, dimmer, friendlyname): #dimmers are not created but only updated from existing switches
    Debug("Device: {}, Dimmer: {}".format(shortaddr, dimmer))
    for Device in Devices:
        if Devices[Device].DeviceID == shortaddr:
           Debug("SwitchType {}".format(Devices[Device].SwitchType))
           if Devices[Device].Type == 244:
               if Devices[Device].SwitchType !=7:
                   Devices[Device].Update(Subtype=73,Switchtype=7,sValue=str(int(dimmer/2.55)),nValue=Devices[Device].nValue)
               Devices[Device].Update(sValue=str(int(dimmer/2.55)),nValue=Devices[Device].nValue)
#               Devices[Device].Update(nValue=power,sValue="On" if power == 1 else "Off")
               Domoticz.Log("Update dimmer {}  {}".format(friendlyname,dimmer))


def createDevice(shortaddr, devicetype, friendlyname, nvalue, svalue):
    Domoticz.Log("Create Device: {} {}".format(friendlyname, devicetype))
    unit = findfreeUnit()
    Domoticz.Device(Name=friendlyname, Unit=unit, TypeName=devicetype, Used=1, DeviceID=shortaddr).Create()
    for Device in Devices:
        if Devices[Device].DeviceID == shortaddr:
           Devices[Device].Update(nValue=nvalue, sValue=svalue)

def findfreeUnit():
    for idx in range(1, 512):
        if idx not in Devices:
            break
    return idx

#def sendZb(shortaddr, command):

####todo: send commands to devices

