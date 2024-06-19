import os
import sys
import threading
import time
import datetime
import serial 
import logging
import requests

logging.basicConfig(
    format='%(threadName)s %(name)s %(levelname)s: %(message)s',
        level=logging.INFO)


def lprint(s): 
    logging.info(s)




def scanUSB():
    devs={}
    for portn in range(3):
        portname=f'/dev/ttyUSB{portn}'
        lprint(f'try open {portname}')
        try:
            with serial.Serial(portname, 115200, timeout=1) as ser:    
                time.sleep(1)
                ser.readline()
                s=ser.readline().decode()
                lprint(s)
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


class mark(threading.Thread):
    def __init__(self,stop_event,port):
        lprint("mark __init__")
        threading.Thread.__init__(self)  
        self.stop_event=stop_event
        self.ok=False        
        self.buf=''
        self.port=port['mark']
        
    def run(self): 
        lprint("run mark")
        with serial.Serial(self.port, 115200, timeout=0.5) as self.markserial:
            while(not self.stop_event.is_set()):
                lprint(f'mark port is {self.markserial._port}')
                tmp=self.markserial.readline()
                if len(tmp)>0:
                    self.buf=tmp.decode()
                    lprint(f'mark read {self.buf}')   
        lprint("Mark closed!!!")
        
    def ask(self):
        firstMeasure=0
        measure=-1
        for i in range(6):
            time.sleep(0.5)
            self.markserial.write(b'?\r')
            time.sleep(0.5)
            if len(self.buf)>0:
                measure=float(self.buf)
            if measure > Fkr:
                grb.soft_reset()
            if abs(firstMeasure-measure)<0.1:
                break
            firstMeasure=measure
        return measure
    



# ****************main ********************
if __name__ == '__main__':


    stop_event = threading.Event()
    
    devs=scanUSB()
    
    if len(devs)<2:
        lprint(f'devs {devs} не достаточно')
        exit()
    lprint(repr(devs))

    mrk=mark(stop_event,devs)
    mrk.start()
    
    while(True):
        force=mrk.ask()
        jforce={'force':force,'forcetime':time.time()}
        lprint(repr(jforce))
        rr=requests.post('http://localhost:5000/forcemeasure',json=jforce) 