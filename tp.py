import serial 
import math
import os
import sys
import threading
import time
import datetime
import logging
import numpy as np
import openpyxl as xl
import OPi.GPIO as g
from pymodbus.client import ModbusSerialClient


xlfilename='test1sp.xlsx'

Yfirststep=5
Ystep=1
Ymax=25

Ycontact=28
Fkr=200 

totalCycles=1000
mesureCycles=20
maxspeed=2500
runspeed=1000






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
    def __init__(self,stop_event):
        print("__init__")
        threading.Thread.__init__(self)  
        self.stop_event=stop_event
        
        self.pack=b''
        self.length=1
    def run(self): 
        print("run grbs")
        for portn in range(3):
            self.port=f'/dev/ttyUSB{portn}'
            try:
                with serial.Serial(self.port, 115200, timeout=1) as self.ser:
                    for i in range(5):
                        time.sleep(1)
                        fs=self.ser.readline()
                        #print(fs.decode())
                        if len(fs)==2:
                            continue
                        if fs.decode()[:4].lower()=="grbl":
                            self.reader()
            except:
                pass
    def reader(self):
        print(f"grb reader run for {self.port}")
        buf=b''
        while(not self.stop_event.is_set()):
            buf=self.ser.readline().decode()
            if len(buf)>0:
                print(buf)
    def write(self,data):
        if type(data)==type('str'):
            data=data.encode()
        x=self.ser.write(data)
        print(f"sent to grbl {x} byte: {data}")
    def soft_reset(self):
        self.write(b'!')
        setmb(76,100)
        time.sleep(1)
        self.write(b'\x18')
        setmb(0x1010,0)
        print("soft reset done")


class mark(threading.Thread):

    def __init__(self,stop_event):
        print("__init__")
        threading.Thread.__init__(self)  
        self.stop_event=stop_event
        self.ok=False        
        self.buf=''
    def run(self): 
        print("run mark")
        
        val=None
        for portn in range(3):
            self.port=f'/dev/ttyUSB{portn}'
            print(f'mark try open {self.port}')
            try:
                with serial.Serial(self.port, 115200, timeout=1) as self.ser:
                    for i in range(5):
                        self.ser.write(b'?\r')
                        time.sleep(1)
                        fs=self.ser.readline()
                        #print(fs.decode())
                        if len(fs)<=2:
                            continue
                        try: 
                            val=float(fs.decode())
                        except:
                            pass
                        if type(val)==type(0.0):
                            print('run reader')
                            self.ok=True
                            self.reader()
    
            except:
                pass

    def reader(self):
        print(f"mark reader run for {self.port}")
        
        while(not self.stop_event.is_set()):
            self.buf=self.ser.readline().decode()
            print(self.buf)

    def write(self,data):
        self.ser.write(data)
    
    def ask(self):
        time.sleep(0.5)
        self.ser.write(b'?\r')
        time.sleep(0.5)
        if float(self.buf) > Fkr:
            grb.soft_reset()           
        return float(self.buf)



def find_edge():
    print("find edge")
    gpIdx.count=1
    gpIdx.stop=0
    grb.write(b"g91g1f1000x1000\n")
    while(gpIdx.count>0):
        print(gpIdx.stop,gpIdx.count,gpIdx.last)
        time.sleep(0.5)
    print("stop at idx")
    time.sleep(2)

def runtest(speed,count):

    gpIdx.stop=0
    gpIdx.count=count
    runmb(speed)
    while(gpIdx.count>0):
        print(gpIdx.stop,gpIdx.count,gpIdx.last)
        time.sleep(0.5)
        
def  xlCreate():
    if not os.path.exists(xlfilename):
        wb=xl.Workbook()
        ws=wb.active
        ws.cell(row=1,column=1,value='datetime')
        ws.cell(row=1,column=2,value='cycles')
        column=3
        for i in range(Yfirststep,Ymax+Ystep,Ystep): #числа только целые
            
            ws.cell(row=1,column=column,value=i)
            column+=1
        wb.save(xlfilename)
        
        
def xlSaveRow(forces,cycle):
    wb=xl.load_workbook(xlfilename)
    ws=wb.active
    for mc in range(1,mesureCycles+1):
        if ws.cell(row=mc,column=1).value==None:
            break
    if mc==2:
        cycles=0
    else:
        cycles=ws.cell(row=mc-1,column=2).value
    cycles+=cycle
    dt=datetime.datetime.now()
    print(f'date is {dt}')
    ws.cell(row=mc,column=1,value=dt) 
    ws.cell(row=mc,column=2,value=cycles) 
    for i in range(len(forces)):
        ws.cell(row=mc,column=i+3,value=forces[i]) 
    wb.save(xlfilename)
        
        
    
        
    
    

def runmesure():
    forces=[]
    print("move y")
    off("ena")
    distance=(Ymax-Yfirststep)
    grb.write(f"g91g1f1000y{Ycontact+Yfirststep}\n".encode())
    for i in range(distance//Ystep):
        grb.write(f"g91g1f1000y{Ystep}\n".encode())
        time.sleep(0.3)
        force=mrk.ask()
        forces.append(force)        
        #print(f' dist {i*Ystep}, force {force}')
    grb.write(f"g91g1f1000y-{distance//Ystep*Ystep}\n".encode())
    time.sleep(3)
    #on("ena")
    return forces



def home_ym():

    off("ena")
    if not gpYm.read_value(): #если не на датчике наедем на него
        grb.write("g91g21g1f500y-50\n") #
        time.sleep(6)
    #останавливается самостоятельно по soft_reset

    for i in range(20):
        if gpYm.read_value(): #уже за датчиком, нужно сойти с датчика
            grb.write("g91g21g1f1000y1\n") #сходим на 1 мм
            time.sleep(1)
            if mrk.ask()>Fkr:
                grb.write("g91g21g1f1000y-1\n")
                
        else:
            break #как только сошли прекращаем движение
            
    grb.write("g91g21g1f1000y0.3\n") 
        
    if gpYm.read_value(): #не сошли с датчика. ошибка
        print("не сошли с датчика. ошибка")
        #stop_event.set()
    else:    
        grb.write("g91g21g1f10y-3\n")
        time.sleep(10)
        if gpYm.read_value():
            print("по оси Y вышли в ноль по датчику (ym)")
        else:
            print("датчик ym не нашли")
            #stop_event.set()
    




# ****************main ********************
if __name__ == '__main__':

    stop_event = threading.Event()
    
    grb=grbs(stop_event)
    grb.start()
    
    gpIdx=gp(stop_event,"idx")
    gpIdx.start()

    gpYp=gp(stop_event,"yp")
    gpYp.start()

    gpYm=gp(stop_event,"ym")
    gpYm.start()
    
    gpIdx.callback_stop=grb.soft_reset
    gpYm.callback_stop=grb.soft_reset
    gpYp.callback_stop=grb.soft_reset

    time.sleep(10)

    mrk=mark(stop_event)
    mrk.start()
    time.sleep(10)
    print(f'mark run is {mrk.ok}')

    cmb=ModbusSerialClient('/dev/ttyS1',parity='E')
    cmb.connect()
    cmb.write_register(0x1010,0x0,1)



            
        
      
        
        



    off("ena")
    on("son")

    time.sleep(5)

    xlCreate()

    home_ym()

    for i in range(2):
        
        cycle=totalCycles//mesureCycles
        
        runtest(runspeed,cycle)
        time.sleep(2)
        find_edge()
        
        xlSaveRow(runmesure(),cycle)
        home_ym()
        

        if stop_event.is_set():
            break
    stop_event.set()
    time.sleep(1)
    
    on("ena")
    off("son")

grb.join()
gpIdx.join()
gpYm.join()
gpYp.join()
mrk.join()



