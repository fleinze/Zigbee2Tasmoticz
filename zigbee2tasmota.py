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


# Decide if zigbee2tasmota.py debug messages should be displayed if domoticz debug is enabled for this plugin
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
            cmdnum= "1" if Command == "On" else "0"
            payload="{ \"device\":"+Devices[Unit].DeviceID+", \"send\":{\"Power\":"+cmdnum+"} }"
            topic = self.prefix[1]+"/ZbSend"
            Domoticz.Log("Send Command {} to {}".format(Command,Devices[Unit].Name))
            Debug("Publish topic {} payload {}".format(topic,payload))
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
                    updateTemp(key,message['ZbReceived'][key]['Temperature'], message['ZbReceived'][key]['Name'])
                if 'Humidity' in message['ZbReceived'][key]:
                    updateHumidity(key, message['ZbReceived'][key]['Humidity'], message['ZbReceived'][key]['Name'])
                if 'BatteryPercentage' in message['ZbReceived'][key]:
                    updateBatteryPercentage(key, message['ZbReceived'][key]['BatteryPercentage'])
#                if 'BatteryVoltage' in message['ZbReceived'][key]:
#                    updateBatteryVoltage(key, message['ZbReceived'][key]['BatteryVoltage'])
                if 'LinkQuality' in message['ZbReceived'][key]:
                    updateLinkQuality(key, message['ZbReceived'][key]['LinkQuality'])
                if 'Power' in message['ZbReceived'][key]:
                    updateSwitch(key, message['ZbReceived'][key]['Power'], message['ZbReceived'][key]['Name'])


###########################
# Tasmota Utility functions


def updateTemp(shortname,temperature,name):
    create=True
    for Device in Devices:
        if Devices[Device].DeviceID == shortname:
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
        createDevice(shortname,devicetype="Temperature",name=name,nvalue=0,svalue="{}".format(temperature))


def updateHumidity(shortname, humidity,name):
    create=True
    if humidity<40:
        humstat="2"
    elif humidity>60:
        humstat="3"
    else:
        humstat="1"
    for Device in Devices:
        if Devices[Device].DeviceID == shortname:
           if Devices[Device].Type == 81: #Humidity
              Devices[Device].Update(nValue=int(humidity), sValue=humstat)
              Domoticz.Log("Update Device {} Humidity {}".format(Devices[Device].Name,humidity))
           elif Devices[Device].Type == 80: #Temperature
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
           create=False
    if create or len(Devices)==0:
        createDevice(shortname,devicetype="Humidity",name=name,nvalue=humidity,svalue="0")

def updateBatteryPercentage(shortname, battery_percentage):
    for Device in Devices:
        if Devices[Device].DeviceID == shortname:
           Devices[Device].Update(nValue=Devices[Device].nValue, sValue=Devices[Device].sValue, BatteryLevel=int(battery_percentage))
           Debug("Update Device {} Battery Percentage: {}".format(Devices[Device].Name, battery_percentage))

#def updateBatteryVoltage(shortname, battery_voltage):
#    Debug("Device: {}, Battery Voltage: {}".format(shortname, battery_voltage))

def updateLinkQuality(shortname, link_quality):
    for Device in Devices:
        if Devices[Device].DeviceID == shortname:
           Devices[Device].Update(nValue=Devices[Device].nValue, sValue=Devices[Device].sValue, SignalLevel=int(link_quality*.12))
           Debug("Device: {}, Link Quality: {}".format(Devices[Device].Name, link_quality))

def updateSwitch(shortname, power, name):
    Debug("Device: {}, Power: {}".format(shortname, power))
    create=True
    for Device in Devices:
        if Devices[Device].DeviceID == shortname:
           if Devices[Device].Type == 244:
               Devices[Device].Update(nValue=power,sValue="On" if power == 1 else "Off")
               Domoticz.Log("Update switch {} nvalue {} svalue {}".format(name,power,"On" if power == 1 else "Off"))
           create=False
    if create or len(Devices)==0:
        createDevice(shortname,devicetype="Switch",name=name,nvalue=power,svalue="")

def createDevice(shortname, devicetype,name,nvalue,svalue):
    Domoticz.Log("Create Device: {} {}".format(name, devicetype))
    unit = findfreeUnit()
    Domoticz.Device(Name=name, Unit=unit, TypeName=devicetype, Used=1, DeviceID=shortname).Create()
    for Device in Devices:
        if Devices[Device].DeviceID == shortname:
           Devices[Device].Update(nValue=nvalue, sValue=svalue)

def findfreeUnit():
    for idx in range(1, 512):
        if idx not in Devices:
            break
    return idx
