from flask import Flask, render_template, request, redirect, url_for,  send_file, Response, jsonify
from flask_bootstrap import Bootstrap
from werkzeug.middleware.proxy_fix import ProxyFix
import threading
import time
import sqlitedict
import openpyxl as xl
import ifcfg


app = Flask(__name__)
app.secret_key = 'your_ssecret_key'

Bootstrap(app)

config=sqlitedict.SqliteDict('config_tf.db')
config.autocommit=True

wanipname ="/home/bfg/data/wanip.conf"      

for x in config:
    print(x, config[x])

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


tp_status={"progress":0,"cycles_done":0,"to_do":"nothing"}


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
    return render_template('index.html',**data|tp_status)

@app.route('/status')
def sendstatus():
    data={}
    for x in tab:
        data[x]=config.get(x,'')   
    return jsonify(data|tp_status)

@app.route('/newtest', methods=['GET'])
def execute_newtest():
    config['snum']=config.get('snum',1)+1
    config['xlname']=f'sp{config["snum"]:06d}.xlsx'
    #wb=xl.load_workbook('sp.xlsx')
    wb=xl.Workbook()
    wb.save(config['xlname'])
    tp_todo="newtest"
    return redirect(url_for('index'))

@app.route('/setspring', methods=['GET'])
def execute_setspring():
    tp_todo="setspring"
    return redirect(url_for('index'))

@app.route('/runtest', methods =['GET'])
def execute_runtest():
    tp_todo="runtest"
    return redirect(url_for('index'))

@app.route('/stoptest',methods =['GET'])
def execute_stoptest():
    tp_todo="stoptest"
    return redirect(url_for('index'))

@app.route('/download',methods =['GET'])
def execute_download():
    return send_file(config['xlname'], as_attachment=True)


@app.route('/progress',methods =['GET'])
def progress():
    def generate():
        while True:
            yield f"data:{g.counter}\n\n"
            
            #yield f"data:{tp_status['progress']}\n\n"
            time.sleep(1)
    return Response(generate(), mimetype= 'text/event-stream')

@app.route('/update_software',methods =['GET'])
def execute_update():
    tp_todo="update_software"
    return redirect(url_for('index'))

@app.route('/reboot',methods =['GET'])
def execute_reboot():
    '            <li class="nav-item"> <a class="nav-link"          href="/reboot">Перезагрузить</a>  </li>'
    tp_todo="reboot"
    return redirect(url_for('index'))


class gp(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.counter=0
        self.stp=False
    def run(self):
        for i in range(100):
            self.counter+=1
            time.sleep(2)
            if self.stp:
                break
    def stop(self):
        self.stp=True
        


if __name__ == '__main__':
    g=gp()
    g.start()
    
    #обновить ip адрес для сервера nginx
    with open(wanipname, "w") as the_file: 
        the_file.write(f"server_name {' '.join([x[1]['inet'] for x in ifcfg.interfaces().items()])};\n")
        
    app.wsgi_app = ProxyFix(app.wsgi_app)    
    app.run(debug=True)
    

