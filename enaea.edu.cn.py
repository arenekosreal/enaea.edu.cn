# 感谢 https://github.com/liulib/enaea.edu.cn 项目提供的研究思路
import requests
import getpass
import time
import hashlib
import os
import json
import logging
import random
import pprint
from requests.utils import dict_from_cookiejar
from bs4 import BeautifulSoup
header={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.67 Safari/537.36 Edg/87.0.664.52",
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"}
default_conf={"auto_login":True,"auto_close_popup":True,"username":None,"password":None,"process_extra":False,"is_debug":False}
os.chdir(os.path.split(os.path.realpath(__file__))[0])
if os.path.exists("config.json")==True:
    with open(file="config.json",mode="r",encoding="utf-8") as conf_reader:
        conf=json.loads(conf_reader.read())
else:
    logging.warning("未找到配置文件，使用默认配置生成文件")
    conf=default_conf
    with open(file="config.json",mode="w",encoding="utf-8") as conf_writer:
        conf_writer.write(json.dumps(conf,sort_keys=True,indent=4))
if bool(conf["is_debug"])==True:
    log_level=logging.DEBUG
else:
    log_level=logging.INFO
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",datefmt="%Y-%m-%d %H:%M:%S",level=log_level)
re_session=requests.session()
def get_time_stamp():
    return str("{:.3f}".format(time.time())).replace(".","")
# 所有自定义类
class enaea_video():
    def __init__(self,data_dic:dict,circle_id:int=0,course_id:int=0):
        self.circle_id=circle_id
        self.course_id=course_id
        try:
            self.id=data_dic["id"]
            self.length=data_dic["length"]
            self.ccvideo_id=data_dic["ccvideoId"]
            self.title=data_dic["filename"]
            self.progress=data_dic["studyProgress"]
            if self.progress==100:
                self.is_finished=True
            else:
                self.is_finished=False
        except KeyError:
            if bool(conf["is_debug"])==True:
                pprint.pprint(data_dic)
            raise ValueError("无法创建视频对象，传入字典格式有误")
class enaea_status():
    def __init__(self,data_dic:dict):
        try:
            self.activity_score=data_dic["activityScore"]
            self.is_required=data_dic["isRequired"]
            self.syllabus_type=data_dic["syllabusType"]
            self.syllabus_name=data_dic["syllabusName"]
            self.syllabus_id=data_dic["syllabusId"]
            self.total_count=data_dic["totalCount"]
            self.used_count=data_dic["usedCount"]
            self.is_select_by_course_module=data_dic["isSelectByCourseModule"]
        except KeyError:
            if bool(conf["is_debug"])==True:
                pprint.pprint(data_dic)
            raise ValueError("无法创建课程状态对象，传入字典格式有误")
        else:
            if self.used_count>=self.total_count:
                self.is_finished=True
            else:
                self.is_finished=False
    def get_details(self,circle_id:int) -> list:
        details=list()
        time_stamp=get_time_stamp()
        pre_re=re_session.get("https://study.enaea.edu.cn/myPageRedirect.do?action=toMyProject&ct="+time_stamp)
        detail_header=header
        detail_header["referer"]=pre_re.url
        time_stamp=get_time_stamp()
        detail_data={"action":"getMyClass","start":0,"limit":20,"isCompleted":None,"circleId":circle_id,"syllabusId":self.syllabus_id,"categortyRemark":"all","_":time_stamp,"_":time_stamp}
        detail_re=re_session.get("https://study.enaea.edu.cn/circleIndex.do",headers=header,params=detail_data)
        detail_list=detail_re.json()["result"]["list"]
        for detail in detail_list:
            details.append(enaea_course_detail(data_dic=detail))
        return details
class enaea_course():
    def __init__(self,data_dic:dict):
        try:
            self.cluster_name=data_dic["clusterName"]
            self.teachers=list()
            for teacher in data_dic["teacherList"]["list"]:
                self.teachers.append(enaea_teacher(data_dic=teacher))
            self.statuses=list()
            for status in data_dic["myCircleStatisticDTOList"]["list"]:
                self.statuses.append(enaea_status(data_dic=status))
            self.circle_card_number=data_dic["circleCardNumber"]
            self.name=data_dic["circleName"]
            self.start_end_time=data_dic["startEndTime"]
            self.cluster_id=data_dic["clusterId"]
            self.circle_id=data_dic["circleId"]
            self.students=list()
            for student in data_dic["studentList"]["list"]:
                self.students.append(enaea_student(data_dic=student))
        except KeyError:
            if bool(conf["is_debug"])==True:
                pprint.pprint(data_dic)
            raise ValueError("无法创建课程对象，传入字典格式有误")
        else:
            for status in self.statuses:
                if status.is_finished==False:
                    self.is_finished=False
                    break
                else:
                    self.is_finished=True
    def get_all_videos(self) -> dict:
        videos=dict()
        details=list()
        for status in self.statuses:
            details.append(status.get_details(circle_id=self.circle_id))
        for detail in details:
            videos[detail.remark]=detail.get_videos(course_id=detail.course_id,circle_id=self.circle_id)
        return videos
class enaea_user():
    def __init__(self):
        try:
            current_user_json=re_session.get("https://study.enaea.edu.cn/getCurrentUser.do",params={"_":get_time_stamp()}).json()
            self.user_name=current_user_json["username"]
            true_header=header
            true_header["referer"]="https://study.enaea.edu.cn/studyCenterRedirect.do?action=showCourseList&username="+self.user_name
            params={"action":"toProfile","username":self.user_name,"ct":get_time_stamp()}
            soup=BeautifulSoup(re_session.get("https://study.enaea.edu.cn/mySpaceRedirect.do",params=params,headers=true_header).text,"html.parser")
            work_info_element=soup.find(name="div",attrs={"id":"jobs_view"})
            safe_info_element=soup.find(name="div",attrs={"id":"contact_view"})
            self.name=current_user_json["screenName"]
            self.work_place=work_info_element.find(name="div",attrs={"id":"work_workUnit"}).text
            self.phone_number=safe_info_element.find(name="div",attrs={"id":"contact_mobile"}).text
            self.email=current_user_json["email"]
            self.photo_url=current_user_json["photoUrl"]
            self.organization_id=current_user_json["organizationId"]
            self.id=current_user_json["id"]
        except:
            raise Exception("无法创建用户对象，获取信息过程出错")
class enaea_teacher():
    def __init__(self,data_dic:dict):
        try:
            self.name=data_dic["screenName"]
            self.desc=data_dic["desc"]
            self.tag=data_dic["tag"]
            self.photo_url=data_dic["accountPhotoUrl"]
            self.id=data_dic["id"]
            self.username=data_dic["username"]
            self.short_name=data_dic["shortName"]
        except KeyError:
            if bool(conf["is_debug"])==True:
                pprint.pprint(data_dic)
            raise ValueError("无法创建教师对象，传入字典格式有误")
class enaea_student():
    def __init__(self,data_dic:dict):
        pass
class enaea_course_detail():
    def __init__(self,data_dic:dict):
        try:
            self.remark=data_dic["remark"]
            self.teacher_name=data_dic["teacherName"]
            self.course_id=data_dic["studyCenterDTO"]["courseId"]
            self.last_study_date=data_dic["studyCenterDTO"]["dateLastStudy"]
            self.id=data_dic["studyCenterDTO"]["id"]
            self.length=data_dic["studyCenterDTO"]["contentLength"]
            self.title=data_dic["studyCenterDTO"]["courseTitle"]
            self.study_progress=data_dic["studyCenterDTO"]["studyProgress"]
            self.syllabus_resource_id=data_dic["syllabusResourceId"]
            self.comment_count=data_dic["commentCount"]
        except KeyError:
            if bool(conf["is_debug"])==True:
                pprint.pprint(data_dic)
            raise ValueError("无法创建课程详细信息对象，传入字典格式有误")
    def get_videos(self,course_id:int,circle_id:int) -> list:
        videos=list()
        course_data={"action":"toCircleIndex","circleId":circle_id,"ct":get_time_stamp()}
        course_header=header
        course_header["referer"]="https://www.enaea.edu.cn/"
        pre_re=re_session.get("https://study.enaea.edu.cn/circleIndexRedirect.do",params=course_data,headers=course_header)
        course_header["referer"]=pre_re.url
        course_data={"courseId":course_id,"circleId":circle_id}
        pre_re=re_session.get("https://study.enaea.edu.cn/viewerforccvideo.do",params=course_data,headers=course_header)
        course_header["referer"]=pre_re.url
        course_data={"action":"getCourseContentList","courseId":course_id,"circleid":circle_id,"_":get_time_stamp()}
        course_re=re_session.get("https://study.enaea.edu.cn/course.do",params=course_data,headers=course_header)
        course_json=course_re.json()
        video_count=course_json["courseContentsTotalCount"]
        logging.info("已获得视频分段数量：%d" %video_count)
        video_list=course_json["result"]["list"]
        for video in video_list:
            videos.append(enaea_video(data_dic=video))
        return videos
def login(session=re_session,auto_login=False) -> tuple:
    logging.info("正在开始登陆账号")
    login_header=header
    login_header["referer"]="https://study.enaea.edu.cn/login.do"
    session.get("https://study.enaea.edu.cn/login.do",headers=login_header)
    if auto_login==False:
        username=input("请输入用户名：")
        password=getpass.getpass("请输入密码（无显示）：")
    else:
        username=str(conf["username"])
        password=str(conf["password"])
    time_stamp=get_time_stamp()
    passwd_digest=hashlib.md5(password.encode("utf-8")).hexdigest()
    able_sky="ablesky_"+time_stamp
    login_data={"ajax":True,
                "jsonp":able_sky,
                "j_username":username,
                "j_password":passwd_digest,
                "_acegi_security_remember_me":False,
                "_":time_stamp}
    try:
        post_re=session.get("https://passport.enaea.edu.cn/login.do",params=login_data,headers=login_header)
    except:
        logging.error("登陆失败，和服务器通信出错，请检查网络连接")
    else:
        return_text=post_re.text
        json_str=return_text.replace(able_sky,"").replace("(","").replace(")","").replace(";","")
        status=json.loads(json_str)["success"]
        if status==True:
            logging.info("登陆成功")
        else:
            logging.error("登陆失败，服务器身份认证出错，请检查你的用户名和密码")
            answer=input("登陆失败，是否重试？Y/n:").upper()
            if answer=="Y":
                logging.info("正在重新登陆")
                login()
            elif answer=="N":
                logging.info("已选择退出")
                exit(0)
            else:
                print("输入错误，请输入Y/y/N/n中的一个字符串，它们分别代表是/是/否/否")
                exit(-1)
    return username,password
def process_study_log(video:enaea_video):
    post_data={"id":video.id,"circleId":video.circle_id,"finish":False,"ct":get_time_stamp()}
    log_post=re_session.post("http://study.enaea.edu.cn/studyLog.do",data=post_data)   
    log_json=log_post.json()  
    if log_json["success"]==True:
        return log_json["process"]
    else:
        return None  
def post_client(video:enaea_video,app_id:str="9E625CB43DE747D0"): 
    cdns=["cd15-ccd1-2.play.bokecc.com"]
    cookies=dict_from_cookiejar(re_session.cookies)
    client_id=cookies["client_id"]
    post_header=header
    post_header["referer"]="https://study.enaea.edu.cn/"
    post_data={ "ua":header["User-Agent"],
                "platform":"h5-pc",
                "uuid":client_id,
                "rid":get_time_stamp(),
                "ver":"v1.0.5",
                "appver":"2.4.3",
                "business":"1001",
                "userid":"",
                "appid":app_id,
                "event":"heartbeat",
                "vid":video.ccvideo_id,
                "retry":0,
                "code":200,
                "cdn":random.sample(cdns,1)[0],
                "heartinter":10,
                "num":64,
                "playerstatus":0,
                "blocktimes":0,
                "blockduration":0}
    re_session.post("https://logger.csslcloud.net/event/vod/v1/client",data=post_data,headers=post_header)
    logging.debug("已发送心跳数据")
def get_status() -> list:
    logging.info("正在开始获取课程列表")
    time_stamp=get_time_stamp()
    true_header=header
    true_header["referer"]="https://study.enaea.edu.cn/login.do"
    params={"ct":time_stamp}
    req=re_session.get("https://study.enaea.edu.cn/myOffice.do",params=params,headers=true_header)
    params={"action":"getMyCircleCourses","limit":3,"start":0,"isFinished":False,"_":get_time_stamp()}
    true_header["referer"]=req.url
    status_req=re_session.get("https://study.enaea.edu.cn/assessment.do",params=params,headers=true_header)
    status_json=status_req.json()
    course_num=status_json["totalCount"]
    logging.info("当前课程数量：%d" %course_num)
    courses=status_json["result"]["list"]
    all_courses=list()
    for course in courses:
        all_courses.append(enaea_course(data_dic=course))
    logging.info("已获取课程列表")
    return all_courses
def process_courses(courses:list):
    logging.info("已开始处理共 %d 门课程" %len(courses))
    for course in courses:
        logging.info("正在处理课程 %s" %course.cluster_name)
        if course.is_finished==True:
            logging.info("课程 %s 已完成" %course.cluster_name)
            continue
        logging.info("课程持续时间 %s" %course.start_end_time)
        for status in course.statuses:
            logging.info("正在处理 %s 部分" %status.syllabus_name)
            if status.is_finished==True:
                logging.info("课程 %s 的 %s 部分已完成" %(course.cluster_name,status.syllabus_name))
                continue
            if status.is_required==False and bool(conf["process_extra"])==False:
                logging.info("课程 %s 的 %s 部分由于非必修并且程序设置为不处理非必修部分而跳过" %(course.cluster_name,status.syllabus_name))
                continue
            for detail in status.get_details():
                logging.info("正在处理小节 %s" %detail.remark)
                for video in detail.get_videos():
                    logging.info("正在处理视频 %s" %video.title)
                    if video.is_finished==True:
                        logging.info("视频 %s 已完成" %video.title)
                        continue
                    video_headers=header
                    video_headers["referer"]="http://study.enaea.edu.cn/viewerforccvideo.do?courseId=%s&circleId=%s" %(video.course_id,video.circle_id)
                    video_data={"action":"statisticForCCVideo","courseId":video.course_id,"circleId":video.circle_id,"_":get_time_stamp()}
                    re_session.get("http://study.enaea.edu.cn/course.do",headers=video_headers,params=video_data)
                    logging.info("视频长度 %s" %video.length)
                    while True:
                        for i in range(6):
                            post_client(video=video)
                            time.sleep(10.0)
                        progress=process_study_log(video=video)
                        logging.debug("已向服务器推送防弹窗数据")
                        if progress==None:
                            logging.debug("进度未达到100，继续处理")
                            continue
                        if progress==100:
                            logging.debug("进度已达到100，终止处理")
                            break
    logging.info("全部课程处理完成")
if __name__=="__main__":
    start_time=time.time()
    user_name,password=login(auto_login=bool(conf["auto_login"]))
    courses=get_status()
    user=enaea_user()
    logging.info("获得用户信息：姓名：%s\t手机号：%s\t用户名：%s" %(user.name,user.phone_number,user.user_name))
    process_courses(courses=courses)
    new_conf={
                "auto_login":bool(conf["auto_login"]),
                "auto_close_popup":bool(conf["auto_close_popup"]),
                "username":str(user_name),
                "password":str(password),
                "process_extra":bool(conf["process_extra"]),
                "is_debug":bool(conf["is_debug"])}
    if new_conf!=conf:
        with open(file="config.json",mode="w",encoding="utf-8") as conf_updater:
            conf_updater.write(json.dumps(new_conf,sort_keys=True,indent=4))
        logging.info("已更新配置文件")
    spent_time=time.time()-start_time
    miniutes,seconds=divmod(spent_time,60)
    hours,miniutes=divmod(miniutes,60)
    logging.info("执行完成，共计花费时间 %2d:%2d:%2d，程序已退出" %(hours,miniutes,seconds))