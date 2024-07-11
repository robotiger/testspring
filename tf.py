from flask import Flask, render_template, request, redirect, url_for,  send_file, Response, jsonify
from flask_bootstrap import Bootstrap
from werkzeug.middleware.proxy_fix import ProxyFix
import threading
import time
import sqlitedict
import openpyxl as xl
import ifcfg
import os


app = Flask(__name__)
app.secret_key = 'your_ssecret_key'

Bootstrap(app)

config=sqlitedict.SqliteDict('config_tf.db')
config.autocommit=True

wanipname ="/home/bfg/data/wanip.conf"      

for x in config:
    print(x, config[x])

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
 'ldistance':'Длина поджатой пружины',
 'xlfilename':'Имя файла протокола',
 'cycles_complete':'Выполнено циклов'
 }


tp_status={"progress":0,"cycles_done":0,"to_do":"nothing","clength":0,"ckx":0,"shrink":0,"force":0}
tmp={}
todotime=time.time()

def settodostatus(status):
    global todotime
    global tp_status
    if time.time()>todotime:
        tp_status["to_do"]=status
        todotime=time.time()+2

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
        config["ldistance"] = float(request.form["ldistance"])
    config_data={}
    for x in tab:
        config_data[x]=config.get(x,'')


    return render_template('index.html',**(config_data|tp_status))

@app.route('/status',methods=['GET', 'POST'])
def sendstatus():
    global tp_status
    if request.method == 'POST':
        for item in tp_status:
            if item != 'force':
                tp_status[item]=request.json.get(item)
    if tp_status["cycles_done"]>=config['cycles']:
        settodostatus("nothing")
    data={}

    for x in config:
        data[x]=config.get(x,'')        
    return jsonify(data|tp_status)

@app.route('/newtest', methods=['GET'])
def execute_newtest():
    config['snum']=config.get('snum',1)+1
    config['xlfilename']=f'sp{config["snum"]:06d}.xlsx'
    #config['cycles_complete']=0 #количество циклов зафиксированное в журнале
    settodostatus("newtest")
    return redirect(url_for('index'))

@app.route('/setspring', methods=['GET'])
def execute_setspring():
    settodostatus("setspring")
    return redirect(url_for('index'))

@app.route('/runtest', methods =['GET'])
def execute_runtest():
    settodostatus("runtest")
    return redirect(url_for('index'))

@app.route('/rtest', methods =['GET'])
def execute_rtest():
    settodostatus("rtest")
    return redirect(url_for('index'))

@app.route('/mtest', methods =['GET'])
def execute_mtest():
    settodostatus("mtest")
    return redirect(url_for('index'))

@app.route('/ktest', methods =['GET'])
def execute_ktest():
    settodostatus("ktest")
    return redirect(url_for('index'))

@app.route('/htest', methods =['GET'])
def execute_htest():
    settodostatus("htest")
    return redirect(url_for('index'))

@app.route('/stest', methods =['GET'])
def execute_stest():
    settodostatus("stest")
    return redirect(url_for('index'))

@app.route('/ctest', methods =['GET'])
def execute_ctest():
    settodostatus("ctest")
    return redirect(url_for('index'))


@app.route('/stoptest',methods =['GET'])
def execute_stoptest():
    settodostatus("stoptest")
    return redirect(url_for('index'))

@app.route('/download',methods =['GET'])
def execute_download():
    if os.path.exists(config['xlfilename']):
        return send_file(config['xlfilename'], as_attachment=True)
    else:
        return redirect(url_for('index'))

@app.route('/update_software',methods =['GET'])
def execute_update():
    settodostatus("update_software")
    return redirect(url_for('index'))

@app.route('/reboot',methods =['GET'])
def execute_reboot():
    settodostatus("reboot")
    return redirect(url_for('index'))
  
@app.route('/progressbar',methods =['GET','POST'])
def progressbar():
    return  jsonify(tp_status)

@app.route('/forcemeasure',methods =['GET','POST'])
def forcemeasure():
    global tp_status
    if request.method == 'POST':
        tp_status['force']=request.json.get('force')
        tp_status['forcetime']=request.json.get('forcetime')
    return jsonify({"result":"stored"})
        



        
if __name__ == '__main__':
    #обновить ip адрес для сервера nginx
    with open(wanipname, "w") as the_file: 
        the_file.write(f"server_name {' '.join(filter(lambda x:not x is None,[x[1]['inet'] for x in ifcfg.interfaces().items()]))};\n")
    app.add_url_rule('/favicon.ico',
                     redirect_to=url_for('static', filename='favicon.ico'))        
    app.wsgi_app = ProxyFix(app.wsgi_app)    
    app.run(debug=True)
    

