# -*- coding: UTF-8 -*-
from flask import Flask,render_template,jsonify,redirect,url_for

import json
from multiprocessing import Process,Pipe 
import time
import os
import subprocess
from apis.mmedu.config import set_mmedu_checkpoints_path,generate_mmedu_code
from extensions import app,socketio
from apis.basenn.config import set_basenn_checkpoints_path,generate_basenn_code,back2pwd,global_varibles





@app.route('/')
def index():
    return redirect(url_for('mmedu.index'),code=301)

@app.route('/basenn/')
def basenn():
    return render_template('basennPage.html',dataset=global_varibles['dataset'])


# 离线轮询
# def poll_log():
#     global shared_data
#     time_stamp = shared_data.get('time_stamp', '')
#     last_line_num = 0
#     print("log_task"+time_stamp)
#     isRunning = shared_data.get('IsRunning', False)
#     log_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) + "\\checkpoints\\" + f"{time_stamp}"
#     json_path = ""
#     while True:
#         json_files = [x for x in os.listdir(log_path) if x.endswith('.json')]
#         if len(json_files) != shared_data['train_times']: # 防止多次训练时，没读取到最新的日志文件
#             time.sleep(1)
#         else:
#             json_path = os.path.join(log_path, json_files[-1])
#             break
#     print("log_path",json_path)
#     while isRunning:
#         if os.path.exists(json_path):
#             with open(json_path, 'r') as f:
#                 lines = f.readlines()
#                 if len(lines) > last_line_num:
#                     for line in lines[last_line_num:]:
#                         log = json.loads(line)
#                         # to str
#                         log = json.dumps(log)
#                         shared_data['message'] = log
#                         print(log)
#                     last_line_num = len(lines)
#             time.sleep(1)
#     print("log_task end")


# 离线轮询
# @app.route('/get_message',methods=['GET'])
# def get_message():

#     global shared_data
#     log_data = shared_data['message']
#     return jsonify(log_data)


mmedu_shared_data = {
    'message':None,
    'IsRunning':False,
    'time_stamp':'',
    'train_times':0,
    "pid":None
}

basenn_shared_data = {
    'message':None,
    'IsRunning':False,
    'time_stamp':'',
    'train_times':0,
    "pid":None
}


mmedu_running_process = None
basenn_running_process = None




def mmedu_train_task(child_conn):
    global mmedu_shared_data
    mmedu_shared_data['IsRunning'] = True
    global mmedu_running_process
    print("training_thread")
    mmedu_shared_data['message'] = "正在训练 ……"
    mmedu_running_process = subprocess.Popen(["..\env\python.exe","mmedu_code.py"],stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(mmedu_running_process.pid)
    child_conn.send(mmedu_running_process.pid)
    mmedu_running_process.communicate()
    print("subprocess end")
    mmedu_shared_data['IsRunning'] = False
    print("isRunning",mmedu_shared_data['IsRunning'])


def basenn_train_task():
    global basenn_shared_data
    basenn_shared_data['IsRunning'] = True
    global basenn_running_process
    print("training_thread")
    print(global_varibles)
    print(basenn_shared_data)
    basenn_running_process = subprocess.Popen(["..\env\python.exe","basenn_code.py"],stdout=subprocess.PIPE, stderr=subprocess.PIPE,encoding='utf-8')
    # 获取子进程输出
    basenn_poll_log_socket(basenn_running_process)
    basenn_running_process = None
    basenn_shared_data['IsRunning'] = False



@socketio.on('log')
def mmedu_poll_log_socket():
    global mmedu_shared_data
    time_stamp = mmedu_shared_data.get('time_stamp', '')
    last_line_num = 0
    print("log_task："+time_stamp)
    isRunning = mmedu_shared_data.get('IsRunning', False)
    log_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) + "\\checkpoints\\" +"mmedu_" +f"{time_stamp}"
    while True:
        json_files = [x for x in os.listdir(log_path) if x.endswith('.json')]
        if len(json_files) != mmedu_shared_data['train_times']: # 防止多次训练时，没读取到最新的日志文件
            time.sleep(1)
        else:
            log_path = os.path.join(log_path, json_files[-1])
            break
    print("log_path",log_path)
    isRunning = mmedu_shared_data['IsRunning']
    print("poll log is running?",isRunning)
    while isRunning:
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                lines = f.readlines()
                if len(lines) > last_line_num:
                    for line in lines[last_line_num:]:
                        log = json.loads(line)
                        log = json.dumps(log)
                        mmedu_shared_data['message'] = log
                        socketio.emit('log',log)
                        print(log)
                    last_line_num = len(lines)
                time.sleep(1)
        else:
            print("log_path not exist")
    print("log_task end")



@socketio.on('log')
def basenn_poll_log_socket(basenn_running_process):
    print("basenn_poll_log_socket")
    flag=True
    while flag:
        line = basenn_running_process.stdout.readline()
        if line:
            socketio.emit('log1',line)
        else:
            flag=False
            break
    return



@app.route('/basenn/start_thread',methods=['GET'])
def basenn_start_thread():
    global basenn_shared_data
    basenn_shared_data['train_times'] += 1
    global basenn_running_process
    if basenn_running_process and basenn_running_process.poll() is None:
        print("已经有一个模型在训练")
        return jsonify({'message': '已经有一个模型在训练'})
    else:
        basenn_shared_data['IsRunning'] = True
        if basenn_shared_data['IsRunning']:
            print("start_thread")
        basenn_train_task()
        return jsonify({'message': '训练已经开始'})


@app.route('/basenn/stop_thread',methods=['GET'])
def basenn_stop_thread():
    if basenn_running_process and basenn_running_process.poll() is None:
        basenn_running_process.terminate()
        return jsonify({'message': '已结束训练','success':True})
    else:
        return jsonify({'message': '没有正在训练的模型','success':False})



running_process = None

@app.route('/mmedu/start_thread',methods=['GET'])
def mmedu_start_thread():
    global mmedu_shared_data
    mmedu_shared_data['train_times'] += 1
    global mmedu_running_process
    if mmedu_running_process and mmedu_running_process.poll() is None:
        print("已经有一个模型在训练")
        return jsonify({'message': '已经有一个模型在训练'})
    else:
        mmedu_shared_data['IsRunning'] = True
        parent_conn, child_conn = Pipe()
        running_process= Process(target=mmedu_train_task,args=(child_conn,))
        running_process.start()
        # print("parent process get id",parent_conn.recv())
        train_pid = parent_conn.recv()
        mmedu_shared_data['pid'] = train_pid
        # mmedu_train_task()
        mmedu_poll_log_socket()
        return jsonify({'message': '训练已经开始'})


@app.route('/mmedu/stop_thread',methods=['GET'])
def mmedu_stop_thread():
    global mmedu_shared_data
    print(mmedu_shared_data)
    # 根据pid结束进程 
    if mmedu_shared_data['pid']:
        os.system("taskkill /pid "+str(mmedu_shared_data['pid'])+" /f")
        mmedu_shared_data['pid'] = None
        return jsonify({'message': '已结束训练'},{'success':True})
    else:
        return jsonify({'message': '没有正在训练的模型','success':False})



@app.route('/mmedu/get_code',methods=['GET'])
def get_mmedu_code():
    global mmedu_shared_data
    print("get_mmedu_code")
    # make dir for checkpoints
    t = time.strftime('%Y%m%d_%H%M%S', time.localtime())
    checkpoints_path = back2pwd(__file__,1) + "\\EasyDL2.0\\checkpoints\\" + "mmedu_"+t
    print("checkpoints_path: ",checkpoints_path)
    os.mkdir(checkpoints_path)
    set_mmedu_checkpoints_path(checkpoints_path=checkpoints_path)
    mmedu_shared_data['time_stamp'] = t
    print("time_stamp",mmedu_shared_data['time_stamp'])
    full_code = generate_mmedu_code()

    return jsonify(full_code)



@app.route('/basenn/get_code',methods=['GET'])
def get_basenn_code():
    global basenn_shared_data
    print("get_basenn_code")
    # make dir for checkpoints
    t = time.strftime('%Y%m%d_%H%M%S', time.localtime())
    checkpoints_path = back2pwd(__file__,1) + "\\EasyDL2.0\\checkpoints\\" + "basenn_"+t
    print("checkpoints_path: ",checkpoints_path)
    os.mkdir(checkpoints_path)
    set_basenn_checkpoints_path(checkpoints_path=checkpoints_path)
    print("global_varibles",global_varibles)
    basenn_shared_data['time_stamp'] = t
    print("time_stamp",basenn_shared_data['time_stamp'])
    full_code = generate_basenn_code()
    return jsonify(full_code)




if __name__ == '__main__':
    app.run(port=5000)
    # socketio.run(app,port=5000)
    # app.run(debug=True,port=5000)
