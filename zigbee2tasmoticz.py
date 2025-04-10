try:
    import collections.abc as collections
except ImportError:  # Python <= 3.2 including Python 2
    import collections

errmsg = ""
try:
    import DomoticzEx as Domoticz
except Exception as e:
    errmsg += "Domoticz core start error: "+str(e)
#try:
#    import json
#except Exception as e:
#    errmsg += " Json import error: "+str(e)
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

        self.prefix = [None, prefix1, prefix2]
        self.mqttClient = mqttClient

        # I don't understand variable (in)visibility
        global Devices
        Devices = devices

    def debug(self, flag):
        global tasmotaDebug
        tasmotaDebug = flag

    # Translate domoticz command to tasmota mqtt command(s?)
    def onDomoticzCommand(self, DeviceID, Unit, Command, Level, Color):
        Debug("Handler::onDomoticzCommand: DeviceID: {}, Unit: {}, Command: {}, Level: {}, Color: {}".format(
            DeviceID, Unit, Command, Level, Color))
        if Devices[DeviceID].Units[Unit].Type == 244:
            if Command == "On" or Command == "Off":
                payload="{ \"Device\":"+DeviceID+", \"Send\":{\"Power\":\""+Command+"\"} }"
                topic = self.prefix[1]+"/ZbSend"
                Domoticz.Log("Send Command {} to {}".format(Command,Devices[DeviceID].Units[Unit].Name))
                Debug("Publish topic {} payload {}".format(topic,payload))
                self.mqttClient.publish(topic, payload)
            elif Command == "Set Level":
                payload="{ \"Device\":"+DeviceID+", \"Send\":{\"Dimmer\":"+str(int(Level*2.55))+"} }"
                topic = self.prefix[1]+"/ZbSend"
                Domoticz.Log("Send Command {} {} to {}".format(Command, str(int(Level*2.55)), Devices[DeviceID].Units[Unit].Name))
                Debug("Publish topic {} payload {}".format(topic,payload))
                self.mqttClient.publish(topic, payload)
                if Level > 0 and Devices[DeviceID].Units[Unit].nValue == 0: #we need to switch it on if it was off
                    payload="{ \"device\":"+DeviceID+", \"send\":{\"Power\":1} }"
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
#                if 'Device' in message['ZbReceived'][key]:
                device = message['ZbReceived'][key]['Device']
#                else:
#                    return
                if 'Name' in message['ZbReceived'][key]:
                    friendlyname = message['ZbReceived'][key]['Name']
                else:
                    friendlyname = message['ZbReceived'][key]['Device']
                if 'Endpoint' in message['ZbReceived'][key]: # and message['ZbReceived'][key]['Endpoint'] > 1:
                    unit = message['ZbReceived'][key]['Endpoint']
                else:
                    unit = 1
                if 'Temperature' in message['ZbReceived'][key]:
                    updateTemp(device, unit ,message['ZbReceived'][key]['Temperature'], friendlyname)
                if 'Humidity' in message['ZbReceived'][key]:
                    updateHumidity(device, unit, message['ZbReceived'][key]['Humidity'], friendlyname)
                if 'BatteryPercentage' in message['ZbReceived'][key]:
                    updateBatteryPercentage(device, unit, message['ZbReceived'][key]['BatteryPercentage'], friendlyname)
                if 'BatteryVoltage' in message['ZbReceived'][key]:
                    updateBatteryVoltage(device, unit, message['ZbReceived'][key]['BatteryVoltage'], friendlyname)
                if 'LinkQuality' in message['ZbReceived'][key]:
                    updateLinkQuality(device, unit, message['ZbReceived'][key]['LinkQuality'], friendlyname)
                if 'Power' in message['ZbReceived'][key]:
                    updateSwitch(device, unit, message['ZbReceived'][key]['Power'], friendlyname)
                if 'Dimmer' in message['ZbReceived'][key]:
                    updateDimmer(device, unit, message['ZbReceived'][key]['Dimmer'], friendlyname)
                if 'Water' in message['ZbReceived'][key]:
                    updateSwitch(device, unit, message['ZbReceived'][key]['Water'], friendlyname)
                if 'Occupancy' in message['ZbReceived'][key]:
                    updateSwitch(device, unit, message['ZbReceived'][key]['Occupancy'], friendlyname)
                if 'Illuminance' in message['ZbReceived'][key]:
                    updateLightsensor(device, unit, message['ZbReceived'][key]['Illuminance'], friendlyname)

    def checkTimeoutDevices(self, timeout):
        now = datetime.now()
        delta = timedelta(minutes=int(timeout))
        for device in Devices:
            if Devices[device].TimedOut == 0:
                if 1 in Devices[device].Units:
                    last = datetime.fromtimestamp(time.mktime(time.strptime(Devices[device].Units[1].LastUpdate, "%Y-%m-%d %H:%M:%S")))
                    if now - last > delta:
                        if Devices[device].Units[1].Type != 244:
                            Debug("Timeout for {}".format(Devices[device].Units[1].Name))
                            Devices[device].TimedOut = 1

###########################
# Tasmota Utility functions


def updateTemp(shortaddr, endpoint, temperature, friendlyname):
    create=True
    if shortaddr in Devices and endpoint in Devices[shortaddr].Units:
        if Devices[shortaddr].TimedOut == 1:
            Devices[shortaddr].TimedOut = 0
        if Devices[shortaddr].Units[endpoint].Type == 80: #Temperature
            Devices[shortaddr].Units[endpoint].nValue = 0
            Devices[shortaddr].Units[endpoint].sValue = "{:.1f}".format(temperature)
            Devices[shortaddr].Units[endpoint].Update(Log=True)
            Domoticz.Log("Update {} {} Temp {}".format(friendlyname,endpoint,temperature))
        elif Devices[shortaddr].Units[endpoint].Type == 81: #Humidity
#            humidity=Devices[shortaddr].Units[endpoint].nValue
            Devices[shortaddr].Units[endpoint].Update(TypeName = "Temp+Hum", UpdateProperties=True)
            Devices[shortaddr].Units[endpoint].sValue = "{:.1f};{};{}".format(temperature, Devices[shortaddr].Units[endpoint].nValue, 0)
            Devices[shortaddr].Units[endpoint].nValue = 0
            Devices[shortaddr].Units[endpoint].Update(Log=True)
            Domoticz.Log("Update Hum {} {} to Temp+Hum sValue {}".format(friendlyname,endpoint,Devices[shortaddr].Units[endpoint].sValue))
        elif Devices[shortaddr].Units[endpoint].Type == 82: #Temp+Hum
            svalue = Devices[shortaddr].Units[endpoint].sValue
            parts=svalue.split(';')
            parts[0]="{:.1f}".format(temperature)
            svalue=";".join(parts)
            Devices[shortaddr].Units[endpoint].nValue = 0
            Devices[shortaddr].Units[endpoint].sValue = svalue
            Devices[shortaddr].Units[endpoint].Update(Log=True)
            Domoticz.Log("Update {} {} sValue {}".format(friendlyname,endpoint,svalue))
        create=False
    if create:
        createDevice(deviceid=shortaddr, unit=endpoint, devicetype="Temperature",name=friendlyname,nvalue=0,svalue="{:.1f}".format(temperature))


def updateHumidity(shortaddr, endpoint, humidity, friendlyname):
    create=True
    if humidity<40:
        humstat="2"
    elif humidity>60:
        humstat="3"
    else:
        humstat="1"
    if shortaddr in Devices and endpoint in Devices[shortaddr].Units:
        if Devices[shortaddr].TimedOut == 1:
            Devices[shortaddr].TimedOut = 0
        if Devices[shortaddr].Units[endpoint].Type == 81: #Humidity
            Devices[shortaddr].Units[endpoint].nValue = int(round(humidity))
            Devices[shortaddr].Units[endpoint].sValue = humstat
            Devices[shortaddr].Units[endpoint].Update(Log=True)
            Domoticz.Log("Update {} {} Hum {}".format(friendlyname,endpoint,humidity))
        elif Devices[shortaddr].Units[endpoint].Type == 80: #Temperature
            temp = Devices[shortaddr].Units[endpoint].sValue
            Devices[shortaddr].Units[endpoint].Update(TypeName = "Temp+Hum", UpdateProperties=True)
            Devices[shortaddr].Units[endpoint].nValue = 0
            Devices[shortaddr].Units[endpoint].sValue = "{};{};{}".format(temp, int(round(humidity)), humstat)
            Devices[shortaddr].Units[endpoint].Update(Log=True)
            Domoticz.Log("Update Temp {} {} to Temp+Hum sValue {}".format(friendlyname,endpoint,Devices[shortaddr].Units[endpoint].sValue))
        elif Devices[shortaddr].Units[endpoint].Type == 82: #Temp+Hum
            svalue=Devices[shortaddr].Units[endpoint].sValue
            parts=svalue.split(';')
            parts[1]=str(int(round(humidity)))
            parts[2]=humstat
            svalue=";".join(parts)
            Devices[shortaddr].Units[endpoint].nValue = 0
            Devices[shortaddr].Units[endpoint].sValue = svalue
            Devices[shortaddr].Units[endpoint].Update(Log=True)
            Domoticz.Log("Update {} {} sValue {}".format(friendlyname,endpoint,svalue))
        create=False
    if create:
        createDevice(deviceid=shortaddr, unit=endpoint, devicetype="Humidity",name=friendlyname,nvalue=int(round(humidity)),svalue=humstat)

def updateLightsensor(shortaddr, endpoint, illuminance, friendlyname):
    create = True
    lux = round(10**(illuminance/10000)-1) # according to zigbee documentation
    if shortaddr in Devices and endpoint in Devices[shortaddr].Units:
        if Devices[shortaddr].TimedOut == 1:
            Devices[shortaddr].TimedOut = 0
        if Devices[shortaddr].Units[endpoint].Type == 246: # Lux
            Devices[shortaddr].Units[endpoint].nValue = 0
            Devices[shortaddr].Units[endpoint].sValue = str(lux)
            Devices[shortaddr].Units[endpoint].Update(Log=True)
            Domoticz.Log("Update {} {} Lux {}".format(friendlyname,endpoint,str(lux)))
        create=False
    if create:
        createDevice(deviceid=shortaddr, unit=endpoint, devicetype="Illumination",name=friendlyname,nvalue=0,svalue=str(lux))

def updateBatteryPercentage(shortaddr, endpoint, battery_percentage, friendlyname):
    if shortaddr in Devices and endpoint in Devices[shortaddr].Units:
        Devices[shortaddr].Units[endpoint].BatteryLevel=int(battery_percentage)
        Devices[shortaddr].Units[endpoint].Update(UpdateProperties=True)
        Domoticz.Log("Update {} {} Batt {}".format(friendlyname,endpoint,battery_percentage))

def updateBatteryVoltage(shortaddr, endpoint, battery_voltage, friendlyname): #do nothing
    Debug("Device: {}, Unit {}, Battery Voltage: {}".format(friendlyname, endpoint, battery_voltage))

def updateLinkQuality(shortaddr, endpoint, link_quality, friendlyname):
    if shortaddr in Devices and endpoint in Devices[shortaddr].Units:
        Devices[shortaddr].Units[endpoint].SignalLevel=int(min(round(link_quality/254*12),12))
        Devices[shortaddr].Units[endpoint].Update(UpdateProperties=True)
        Debug("Update {} {} LQI {}".format(friendlyname,endpoint,link_quality))

def updateSwitch(shortaddr, endpoint, power, friendlyname):
    create=True
    if shortaddr in Devices and endpoint in Devices[shortaddr].Units:
        if  Devices[shortaddr].Units[endpoint].Type == 244:
            if  Devices[shortaddr].Units[endpoint].SwitchType == 7:
                Devices[shortaddr].Units[endpoint].nValue = power
                Devices[shortaddr].Units[endpoint].Update(Log=True)
            else:
                Devices[shortaddr].Units[endpoint].nValue = power
                Devices[shortaddr].Units[endpoint].sValue = "On" if power == 1 else "Off"
                Devices[shortaddr].Units[endpoint].Update(Log=True)
            Domoticz.Log("Update {} {} Power {}".format(friendlyname,endpoint,power))
        create=False
    if create:
        createDevice(deviceid=shortaddr, unit=endpoint, devicetype="Switch",name=friendlyname,nvalue=power,svalue="")

def updateDimmer(shortaddr, endpoint, dimmer, friendlyname): #dimmers are not created but only updated from existing switches
    Debug("Device: {}, Dimmer: {}".format(shortaddr, dimmer))
    if shortaddr in Devices and endpoint in Devices[shortaddr].Units:
        if Devices[shortaddr].Units[endpoint].Type == 244:
            if Devices[shortaddr].Units[endpoint].SwitchType != 7:
                Devices[shortaddr].Units[endpoint].Update(TypeName="Dimmer", SuppressTriggers=True)
                Debug("Update {} to Dimmer".format(friendlyname))
            Devices[shortaddr].Units[endpoint].sValue = str(int(round(dimmer/2.55)))
            Devices[shortaddr].Units[endpoint].Update(Log=True)
            Domoticz.Log("Update {} {} Dimmer {}".format(friendlyname,endpoint,str(int(round(dimmer/2.55)))))


def createDevice(deviceid, unit, devicetype, name, nvalue, svalue):
    Domoticz.Log("Create Device: {} {}".format(name, devicetype))
    Domoticz.Unit(Name=name, DeviceID=deviceid, Unit=unit, TypeName=devicetype, Used=1).Create()
    Devices[deviceid].Units[unit].nValue = nvalue
    Devices[deviceid].Units[unit].sValue = svalue
    Devices[deviceid].Units[unit].Update(Log=True)

