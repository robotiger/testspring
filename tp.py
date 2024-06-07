from flask import Flask, render_template, request, redirect, url_for,  send_file, Response
from flask_bootstrap import Bootstrap
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
import sqlitedict
import ifcfg
import requests
import numpy as np
from scipy.optimize import minimize



config=sqlitedict.SqliteDict('config_tf.db')
#config.autocommit=True

logname='/home/bfg/data/ts.log'

    
#Yfirststep=5
#Ystep=1
#Ymax=24

Ycontact=27.5
Fkr=200 

totalCycles=200
mesureCycles=20
maxspeed=2500
runspeed=1200

status={"progress":0,"cycles_done":0,"to_do":"nothing","clength":0,"ckx":0,"shrink":0}


grb=None
gpp=None
cmb=None
mrk=None

used_gpio_pins={"son":7,"ena":12,"idx":26,"yp":15,"ym":22}


def logInf(s): 
    print(s)
    #loglenmax=10000000   
    #logging.basicConfig(format='%(asctime)s | %(message)s', datefmt='%Y/%m/%d %H: %M: %S ', filename=logname, level=logging.INFO)
    #logging.info(s)
    
    #app.logger.info(s)
    #try: 
        #statinfo= os.stat(logname)

        #if statinfo.st_size >loglenmax: 
            #os.rename(logname, lognameold)
            #logging.shutdown()
            #logging.basicConfig(format='%(asctime)s | %(message)s', datefmt='%Y/%m/%d %H: %M: %S ', filename=logname, level=logging.INFO)
    #except: 
        #pass



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
        logInf("grbs __init__ ")
        threading.Thread.__init__(self)  
        self.stop_event=stop_event
        
        self.pack=b''
        self.length=1
    def run(self): 
        logInf("run grbs")
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
        logInf(f"grb reader run for {self.port}")
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

    def __init__(self,stop_event):
        logInf("mark __init__")
        threading.Thread.__init__(self)  
        self.stop_event=stop_event
        self.ok=False        
        self.buf=''
    def run(self): 
        logInf("run mark")
        
        val=None
        for portn in range(3):
            self.port=f'/dev/ttyUSB{portn}'
            logInf(f'mark try open {self.port}')
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
                            self.ok=True
                            break
                    if self.ok:
                        self.reader()
    
            except:
                pass


    def reader(self):
        logInf(f"mark reader run for {self.port}")
        
        while(not self.stop_event.is_set()):
            self.buf=self.ser.readline().decode()
            #print(self.buf)

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


class measures(threading.Thread):
    
    def __init__(self,stop_event):
        threading.Thread.__init__(self)
        self.stop_event=stop_event   
        self.atHome=False
        
    def find_edge(self):
        logInf("start find edge")
        gpIdx.count=1
        gpIdx.stop=0
        grb.write(b"g91g1f1000x1000\n")
        while(gpIdx.count>0):
            #print(gpIdx.stop,gpIdx.count,gpIdx.last)
            time.sleep(0.5)
        logInf("edge found rotation stop at idx")
        time.sleep(2)
    
    def runtest(self,speed,count):
    
        gpIdx.stop=0
        gpIdx.count=count
        runmb(speed)
        while(gpIdx.count>0):
            #print(gpIdx.stop,gpIdx.count,gpIdx.last)
            time.sleep(0.5)        

    def runmesure(self):
        forces=[]
        logInf("move y ")
        off("ena")
        distance=(config['lmax']-config['lmin'])
        grb.write(f"g91g1f1000y{Ycontact+config['lmin']}\n".encode())
        #input('pause before mesure')
        for i in range(distance//config['lstep']):

            grb.write(f"g91g1f1000y{config['lstep']}\n".encode())
            time.sleep(0.1)
            force=mrk.ask()
            forces.append(force)        
            logInf(f" dist {i*config['lstep']}, force {force}")
        grb.write(f"g91g1f1000y-{i*config['lstep']}\n".encode())
        time.sleep(3)
        #on("ena")
        return forces
    
    
    
    def home_ym(self):
        self.atHome=False
        off("ena")
        time.sleep(5)
        if not gpYm.read_value(): #если не на датчике наедем на него
            grb.write("g91g21g1f1000y-60\n") #
            time.sleep(10)
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
        time.sleep(0.5)    
        if gpYm.read_value(): #не сошли с датчика. ошибка
            logInf("не сошли с датчика. ошибка")
            #stop_event.set()
        else:    
            grb.write("g91g21g1f10y-3\n")
            time.sleep(10)
            if gpYm.read_value():
                logInf("по оси Y вышли в ноль по датчику (ym)")
                self.atHome=True
            else:
                logInf("датчик ym не нашли")
                #stop_event.set()
                
    #def  xlCreate(self):
        #if not os.path.exists(xlfilename):
            #wb=xl.Workbook()
            #ws=wb.active
            #ws.cell(row=1,column=1,value='datetime')
            #ws.cell(row=1,column=2,value='cycles')
            #column=3
            #for i in range(Yfirststep,Ymax+Ystep,Ystep): #числа только целые
                #ws.cell(row=1,column=column,value=i)
                #column+=1
            #wb.save(xlfilename)
            
            
  
                
    def run_test(self):
        off("ena")
        on("son")
    
        time.sleep(5)
    
        self.xlMakeHeader()
        self.home_ym()
        if not self.atHome:
            self.home_ym()
        self.cycles=0
        #input('pause')
        while(True):
            runspeed= int(config["freq"]*38*60/17)

            if status['to_do']=='stoptest':
                break                 
            self.runtest(runspeed,config["cyclesbetween"])
            time.sleep(2)
            if status['to_do']=='stoptest':
                break                 
            self.find_edge()
            
            cycles=self.xlSaveRow(self.runmesure())
            logInf(f"do {cycles} cycles")
            if status['to_do']=='stoptest':
                break            
            self.home_ym()
            if status['to_do']=='stoptest':
                break                 
        
            if cycles>config["cycles"]:
                break
            if stop_event.is_set():
                break
        time.sleep(1)
        
        on("ena")
        off("son")        
        
        
    def xlMakeHeader(self):
        if os.path.exists(config['xlfilename']):
            wb=xl.load_workbook(config['xlfilename'])
        else:
            wb=xl.Workbook()
        
        ws=wb.active
        
        ws.cell(row=1,column=5,value='Протокол тестирования пружины')
        ws.cell(row=1,column=10,value=datetime.datetime.now())
        
        row=2
        tab={
         'snum': 'Номер теста',
         'sname': 'Наименование',
         'slength': 'Длина',
         'sdiameter': 'Диаметр пружины',
         'sdp': 'Толщина прутка',
         'snrot': 'Число витков',
         'smatherial': 'Материал',
         'skxnom': 'Номинальный коэфф жесткости',
         'cycles': 'Число циклов сжатия',
         'cyclesbetween': 'Число циклов сжатия между измерениями',
         'freq': 'Частота сжатия',
         'lmin': 'Начальное сжатие',
         'lmax': 'Максимальное сжатие',
         'lstep': 'Шаг измерения усилия пружины',
         }
        
        for t in tab:
            ws.cell(row=row,column=1,value=tab[t])
            ws.cell(row=row,column=5,value=config[t])
            row+=1
        
        ws.cell(row=row,column=1,value='Дата')
        ws.cell(row=row,column=2,value='Циклы')
        ws.cell(row=row,column=3,value='Длина')
        ws.cell(row=row,column=4,value='Кх')
        ws.cell(row=row,column=5,value='Усадка')
    
        column=6
        sx=list(range(config['lmin'],config['lmax']+config['lstep'],config['lstep']))
        config['sx']=sx
        for i in sx: 
            #числа только целые пока
            
            ws.cell(row=row,column=column,value=i)
            column+=1  
        config['startrow']=row+1    
        wb.save(config['xlfilename'])
    
    def xlSaveRow(self,forces):
        global status
        wb=xl.load_workbook(config['xlfilename'])
        ws=wb.active
        
        config['cycles_complete']+=config["cyclesbetween"]
        gpIdx.count=config["cyclesbetween"] #чтобы прогресс не скакал а двигался плавно
        mc=config['startrow']
        
        #немного расчетов
        def f(x,sx,sf):
            return ((sx*x[0]+x[1]-sf)**2).sum()
        res=minimize(f,x0=[3,3],args=(np.array(config['sx']),np.array(forces)))
        ckx=res.x[0]
        clength=res.x[1]/res.x[0]+config["ldistance"]
        # сохраняем результаты расчета в статус для обновления веб страницы
        status['ckx']=ckx
        status['clength']=clength
        status['shrink']=config['slength']-clength

        #заполняем строку данными
        ws.cell(row=mc,column=1,value=datetime.datetime.now()) 
        ws.cell(row=mc,column=2,value=config['cycles_complete']) 
        ws.cell(row=mc,column=3,value=clength) 
        ws.cell(row=mc,column=4,value=ckx) 
        ws.cell(row=mc,column=4,value=config['slength']-clength) 
        
        
        for i in range(len(forces)):
            ws.cell(row=mc,column=i+6,value=forces[i]) 
            
        config['startrow']+=1
        wb.save(config['xlfilename'])
        return cycles     


class webrun(threading.Thread):
    def __init__(self,stop_event):
        threading.Thread.__init__(self)
        self.stop_event=stop_event

    def run(self):
        global status
        res_ok=False
        while(not self.stop_event.is_set()):
            try:
                res=requests.get('http://localhost:5000/status')
                if res.ok:
                    newstatus=res.json()
                    res_ok=res.ok
                status['to_do']=newstatus['to_do']
                #print(f"got status to_do {newstatus['to_do']}")
            except:
                print("отключено приложение веб")
            if res_ok:
                if gpIdx.count>=0:
                    status['cycles_done']=config["cycles_complete"]+config["cyclesbetween"]-gpIdx.count
                else:
                    status['cycles_done']=0
                    
                if status['cycles_done']>0:
                    status['progress']=status['cycles_done']*100//config["cycles"]
                else:
                    status['progress']=0
                try:
                    rr=requests.post('http://localhost:5000/status',json=status) 
                    #print(f"sent status {status}")
                    
                except:
                    print("отключено приложение веб")            
            time.sleep(1)
    



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
    #print(f'mark run is {mrk.ok}')
    
    cmb=ModbusSerialClient('/dev/ttyS1',parity='E')
    cmb.connect()
    cmb.write_register(0x1010,0x0,1)
    
    ms=measures(stop_event)
    
    web=webrun(stop_event)
    web.start()

    while(True):

        print(f"main {status['to_do']}")
        if status['to_do']=='setspring':
            ms.find_edge()
            ms.home_ym()
            status['to_do']='nothing'
            
        if status['to_do']=='runtest':
            ms.run_test()
            status['to_do']='nothing'            
   

        time.sleep(1)
        


def joins():
    grb.join()
    gpIdx.join()
    gpYm.join()
    gpYp.join()
    mrk.join()



