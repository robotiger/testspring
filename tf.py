from flask import Flask, render_template, request, redirect, url_for,  send_file, Response
from flask_bootstrap import Bootstrap
import threading
import time
import sqlitedict
import openpyxl as xl

app = Flask(__name__)
app.secret_key = 'your_ssecret_key'

Bootstrap(app)

config=sqlitedict.SqliteDict('config_tf.db')
config.autocommit=True

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

def tph(t):
    if t==float:
        return "number step=0.001"
    if t==int:
        return "number"
    if t==str:
        return "text"

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
    return render_template('indexf.html',**data)

@app.route('/newtest', methods=['GET', 'POST'])
def execute_newtest():
    config['snum']=config.get('snum',1)+1
    config['xlname']=f'sp{config["snum"]:06d}.xlsx'
    wb=xl.load_workbook('sp.xlsx')
    wb.save(config['xlname'])
    return redirect(url_for('index'))

@app.route('/setspring', methods=['GET', 'POST'])
def execute_setspring():
    print('start setspring')
    ra='setspring'
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
    return send_file(config['xlname'], as_attachment=True)


@app.route('/progress')
def progress():
    def generate():
        while True:
            yield f"data:{config['progress']}\n\n"
            time.sleep(5)
    return Response(generate(), mimetype= 'text/event-stream')


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
    app.run(debug=True)
    

