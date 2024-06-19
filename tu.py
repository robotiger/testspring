import os
import sys
import threading
import time
import datetime
import serial 
import logging
import numpy as np
import openpyxl as xl
import OPi.GPIO as g
from pymodbus.client import ModbusSerialClient
import sqlitedict
import ifcfg
import requests
from scipy.optimize import minimize


Ycontact=27.5
Fkr=200 

status={"progress":0,"cycles_done":0,"to_do":"nothing","clength":0,"ckx":0,"shrink":0,"status":""}
config={}

grb=None
gpp=None
cmb=None
mrk=None

used_gpio_pins={"son":7,"ena":12,"idx":26,"yp":15,"ym":22}


#Переключение вывода на выход и выдача на него единицы
def on(pin):
    if type(pin)==type("str"):
        pin=used_gpio_pins.get(pin)
    if pin:
        g.setup(pin,g.OUT)
        g.output(pin,1)
        g.cleanup(pin)  
    
def off(pin):
    if type(pin)==type("str"):
        pin=used_gpio_pins.get(pin)
    if pin:    
        g.setup(pin,g.OUT)
        g.output(pin,0)
        g.cleanup(pin)  


def read_value(pin):
    val=None
    if type(pin)==type("str"):
        pin=used_gpio_pins.get(pin)
    if pin:    
        g.setup(pin,g.IN)
        val=g.input(pin)
        g.cleanup(pin)
    return val

def logInf(s): 
    print(s)


def setmb(adr,val):
    if cmb:
        cmb.write_register(adr,val,1)


def runmb(speed):
    runspeed=speed
    setmb(75,maxspeed)
    setmb(76,min(speed//2,maxspeed))
    setmb(0x1010,0x1234)
    setmb(0x1010,0x2222)
    time.sleep(0.5)
    setmb(76,min(speed,maxspeed))

# A class that extends the Thread class
class gp(threading.Thread):
    def __init__(self,stop_event,pin):
        threading.Thread.__init__(self)
        self.stop_event=stop_event
        
        if type(pin)==type("str"):
            self.name=pin
            pin=used_gpio_pins.get(pin)        
        self.pin=pin
        g.setwarnings(False)
        g.setmode(g.BOARD)
        g.setup(self.pin,g.IN)
        self.count=0
        self.tlp=time.time()
        self.last=0
        self.stop=0
        self.freq=0
        self.callback_stop=None
    def run(self):
        while(not self.stop_event.is_set()):
            self.last<<=1
            self.last|=g.input(self.pin)
            self.last&=0xff
            if self.last==0x7:
                if self.name=='idx':
                    self.count-=1
                else:
                    self.count=0
                if self.count<=0:
                    if self.callback_stop :
                        self.callback_stop()                    
            time.sleep(0.001)
    def read_value(self):
            return g.input(self.pin)

class grbs(threading.Thread):
    def __init__(self,stop_event,devs):
        logInf("grbs __init__ ")
        threading.Thread.__init__(self)  
        self.stop_event=stop_event
        self.port=devs['grbl']
        self.pack=b''
        self.length=1
    def run(self): 
        logInf("run grbs")
        with serial.Serial(self.port, 115200, timeout=1) as self.ser:
            buf=b''
            while(not self.stop_event.is_set()):
                buf=self.ser.readline().decode()
                if len(buf)>0:
                    logInf(f'grbs rcv {buf}')
                    
    def write(self,data):
        if type(data)==type('str'):
            data=data.encode()
        x=self.ser.write(data)
        logInf(f"sent to grbl {x} byte: {data}")
    def soft_reset(self):
        self.write(b'!')
        setmb(76,100)
        time.sleep(1)
        self.write(b'\x18')
        setmb(0x1010,0)
        logInf("soft reset done")


class mark(threading.Thread):

    def __init__(self,stop_event,port):
        logInf("mark __init__")
        threading.Thread.__init__(self)  
        self.stop_event=stop_event
        self.ok=False        
        self.buf=''
        self.port=port['mark']

    def run(self): 
        logInf("run mark")
        
        val=None
        with serial.Serial(self.port, 115200, timeout=1) as self.ser:
            while(not self.stop_event.is_set()):
                self.buf=self.ser.readline().decode()
                print("mark read",self.buf)            
            
        print("Mark closed!!!")
        

    def write(self,data):
        self.ser.write(data)
    
    def ask(self):
        firstMeasure=0
        for i in range(6):
            time.sleep(0.5)
            self.ser.write(b'?\r')
            time.sleep(0.5)
            measure=float(self.buf)
            if measure > Fkr:
                grb.soft_reset()
                
            if abs(firstMeasure-measure)<0.1:
                break
            firstMeasure=measure
        return measure
    
def scanUSB():
    devs={}
    for portn in range(3):
        portname=f'/dev/ttyUSB{portn}'
        print(f'try open {portname}')
        try:
            with serial.Serial(portname, 115200, timeout=1) as ser:    
                
                time.sleep(1)
                ser.readline()
                s=ser.readline().decode()
                print(s)
                if len(s)>0:
                    if s[:4]=="Grbl":
                        devs["grbl"]=portname
                ser.write(b'?\r')
                time.sleep(1)
                s=ser.readline().decode()
                if s[:1]=='0':
                    devs["mark"]=portname
        except:
            pass
    return devs


# ****************main ********************
if __name__ == '__main__':


    stop_event = threading.Event()
    
    devs=scanUSB()
    
    if len(devs)<2:
        print(f'devs {devs} не достаточно')
        exit()
    print(devs)
    time.sleep(10)
    
   
    gpIdx=gp(stop_event,"idx")
    gpIdx.start()
    
    gpYp=gp(stop_event,"yp")
    gpYp.start()
    
    gpYm=gp(stop_event,"ym")
    gpYm.start()
    
    gpIdx.callback_stop=grb.soft_reset
    gpYm.callback_stop=grb.soft_reset
    gpYp.callback_stop=grb.soft_reset    
    
    cmb=ModbusSerialClient('/dev/ttyS1',parity='E')
    cmb.connect()
    cmb.write_register(0x1010,0x0,1)    
    
    grb=grbs(stop_event,devs)
    grb.start()    
    
    mrk=mark(stop_event,devs)
    mrk.start()
    
    
    for i in range(1000):
        print(mrk.ask())
        grb.write("g91g21g1f1000y1\n") 
        time.sleep(1)
        grb.write("g91g21g1f1000y-1\n") 
        time.sleep(1)
        