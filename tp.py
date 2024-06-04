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


app = Flask(__name__)
app.secret_key = 'your_ssecret_key'

Bootstrap(app)

config=sqlitedict.SqliteDict('config_tf.db')
config.autocommit=True

logname='/home/bfg/data/ts.log'
wanipname ="/home/bfg/data/wanip.conf"
    
Yfirststep=5
Ystep=1
Ymax=24

Ycontact=28
Fkr=200 

totalCycles=200
mesureCycles=20
maxspeed=2500
runspeed=1200

tab={ "snum":{"name":"Номер теста","typ":int,"cla":""},
"sname":{"name":"Наименование","typ":str,"cla":"table-active"},
"slength":{"name":"Длина","typ":float,"cla":"table-active"},
"sdiameter":{"name":"Диаметр пружины","typ":float,"cla":"table-active"},
"sdp":{"name":"Толщина прутка","typ":float,"cla":"table-active"},
"snrot":{"name":"Число витков","typ":float,"cla":"table-active"},
"smatherial":{"name":"Материал","typ":str,"cla":"table-active"},
"skxnom":{"name":"Номинальный коэфф жесткости","typ":float,"cla":"table-success"},
"cycles":{"name":"Число циклов сжатия","typ":int,"cla":"table-success"},
"cyclesbetween":{"name":"Число циклов сжатия между измерениями","typ":int,"cla":"table-success"},
"freq":{"name":"Частота сжатия","typ":float,"cla":"table-success"},
"lmin":{"name":"Начальное сжатие","typ":int,"cla":"table-success"},
"lmax":{"name":"Максимальное сжатие","typ":int,"cla":"table-success"},
"lstep":{"name":"Шаг измерения усилия пружины","typ":int,"cla":"table-success"},
"docycles":{"name":"Выполнено циклов сжатия","typ":int,"cla":"table-primary"},
"clen":{"name":"Расчетная длина пружины","typ":float,"cla":"table-primary"},
"ckx":{"name":"Коэффициент жесткости","typ":float,"cla":"table-primary"},
"shrink":{"name":"Усадка","typ":float,"cla":"table-primary"},
    }





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
        for i in range(distance//config['lstep']+config['lstep']):
            grb.write(f"g91g1f1000y{config['lstep']}\n".encode())
            time.sleep(0.1)
            force=mrk.ask()
            forces.append(force)        
            logInf(f" dist {i*config['lstep']}, force {force}")
        grb.write(f"g91g1f1000y-{distance//config['lstep']*config['lstep']+config['lstep']}\n".encode())
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
    
        self.xlCreate()
        self.home_ym()
        if not self.atHome:
            self.home_ym()
        self.cycles=0
        #input('pause')
        for i in range(mesureCycles+1):
            cycle=totalCycles//mesureCycles
            self.runtest(runspeed,cycle)
            time.sleep(2)
            self.find_edge()
            
            cycles=xlSaveRow(self.runmesure(),cycle)
            logInf(f"do {cycles} cycles")
            self.home_ym()
            if not self.atHome:
                self.home_ym()            
            if cycles>totalCycles:
                break
    
            if stop_event.is_set():
                break
            
        stop_event.set()
        time.sleep(1)
        
        on("ena")
        off("son")        
        
        



def updateip(): 
    ip=[]

    #получить ip адрес глобальный если есть
    #resp=requests.get('http://api.ipify.org')
    #if resp.status_code == 200: 
        #ip.append(resp.text)
    
    #получить ip адрес локальный
    for i in ifcfg.interfaces().items(): 
        if not i[1]['inet'] is None: 
            ip.append(i[1]['inet'])
      
    #logi(f"config wan ip {ip}")     
    # print("store wanip", ip)
    with open(wanipname, "w") as the_file: 
        the_file.write(f"server_name {' '.join(ip)};\n")

def xlMakeHeader():
    wb=xl.load_workbook(config['xlfilename'])
    ws=wb.active
    
    ws.cell(row=1,column=5,value='Протокол тестирования пружины')
    ws.cell(row=1,column=10,value=datetime.datetime.now())
    
    row=2
    for t in tab:
        if t['cla']!="table-primary":
            ws.cell(row=row,column=1,value=tab[t]['name'])
            ws.cell(row=row,column=5,value=config[tab[t]])
    
    row+=1
    
    ws.cell(row=row,column=1,value='Дата')
    ws.cell(row=row,column=2,value='Циклы')
    ws.cell(row=row,column=3,value='Длина')
    ws.cell(row=row,column=4,value='Кх')
    ws.cell(row=row,column=5,value='Усадка')

    column=6
    for i in range(config['lmin'],config['lmax']+config['lstep'],config['lstep']): #числа только целые
        ws.cell(row=1,column=column,value=i)
        column+=1  
    config['startrow']=row+1    
    wb.save(config['xlfilename'])

def xlSaveRow(self,forces,cycle):
    wb=xl.load_workbook(config['xlfilename'])
    ws=wb.active
    mesureCycles=config['cycles']//config['cyclesbetween']+1
    for mc in range(config['startrow'],config['startrow']+mesureCycles): 
        if ws.cell(row=mc,column=1).value==None:
            break
    if mc==config['startrow']:
        cycles=0
    else:
        cycles=ws.cell(row=mc-1,column=2).value
    cycles+=cycle
    dt=datetime.datetime.now()
    print(f'date is {dt}')
    ws.cell(row=mc,column=1,value=dt) 
    ws.cell(row=mc,column=2,value=cycles) 
    for i in range(len(forces)):
        ws.cell(row=mc,column=i+6,value=forces[i]) 
    wb.save(config['xlfilename'])
    return cycles     

#************************ flask

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        config["sname"] = request.form["sname"]
        config["slength"] = float(request.form["slength"])
        config["sdiameter"] = float(request.form["sdiameter"])
        config["sdp"] = float(request.form["sdp"])
        config["snrot"] = float(request.form["snrot"])
        config["smatherial"] = request.form["smatherial"]
        config["skxnom"] = float(request.form["skxnom"])
        config["cycles"] = int(request.form["cycles"])
        config["cyclesbetween"] = int(request.form["cyclesbetween"])
        config["freq"] = float(request.form["freq"])
        config["lmin"] = int(request.form["lmin"])
        config["lmax"] = int(request.form["lmax"])
        config["lstep"] = int(request.form["lstep"])
    data={}
    for x in tab:
        data[x]=config.get(x,'')
        
    data['docycles']=150000
    if data['cycles']>0:
        config['progress']=data['docycles']*100//data['cycles']
    else:
        config['progress']=0
    return render_template('index.html',**data)

@app.route('/newtest', methods=['GET', 'POST'])
def execute_newtest():
    config['snum']=config.get('snum',1)+1
    config['xlfilename']=f'sp{config["snum"]:06d}.xlsx'
    wb=xl.load_workbook('sp.xlsx')
    wb.save(config['xlfilename'])
    
    xlMakeHeader()
    return redirect(url_for('index'))

@app.route('/setspring', methods=['GET', 'POST'])
def execute_setspring():
    ms.home_ym()
    ms.find_edge()
    return redirect(url_for('index'))

@app.route('/runtest', methods =['GET', 'POST'])
def execute_runtest():
    print('start setspring')
    ra='setspring'
    return redirect(url_for('index'))

@app.route('/stoptest')
def execute_stoptest():
    print('start setspring')
    ra='setspring'
    return redirect(url_for('index'))

@app.route('/download')
def execute_download():
    return send_file(config['xlfilename'], as_attachment=True)


@app.route('/progress')
def progress():
    def generate():
        while True:
            yield f"data:{config['progress']}\n\n"
            time.sleep(5)
    return Response(generate(), mimetype= 'text/event-stream')


# ****************main ********************
if __name__ == '__main__':

    updateip()
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
    ms.run()
    
    app.run(debug=True)

def joins():
    grb.join()
    gpIdx.join()
    gpYm.join()
    gpYp.join()
    mrk.join()



