from os import access
import requests
import json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DATETIME, VARCHAR
from app.models import db

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from app.reservation.model import Reservation, RsvState
from app.auth.model import User
from app.item.model import Item
from config import WX_SUBSC_TPL_ID as SUBSC_TPL_ID

SHA_TZ = timezone(timedelta(hours=8), name='Asia/Shanghai',)

def currentTime():
    # 返回北京时间
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    return utc_now.astimezone(SHA_TZ)

# class AccessToken(db.Model):
#     __tablename__ = "access_token"

#     token = db.Column(VARCHAR(512), nullable=False)
#     expiryTime = db.Column(DATETIME, nullable=False)

class _ATManager():
    def __init__(self, appID, appSecret):
        self.appID = appID
        self.appSecret = appSecret

    def _getAccessToken(self):
        rtn = {}

        url = ("http://api.weixin.qq.com/cgi-bin/token?grant_type="
                "client_credential&appid=%s&secret=%s" % (self.appID, self.appSecret))
        res = requests.get(url).json()
        if res.has_key('access_token'):
            rtn['result'] = "succeeded."
            rtn['access_token'] = res['access_token']
        else:
            rtn['result'] = "failed."
            rtn.update(res)

        return rtn

    def getAccessToken(self):
        """
            a naive method to get access token
        """
        return self._getAccessToken()['access_token']


def sendRsvSubscMsg(rsv:Reservation):
    """
    Args:
        touserId: touser's openID
        rsv: the reservation object
    
    Returns:
        A json Object:
        { 
            "errcode":
            "errmsg:
        }
        API "https://api.weixin.qq.com/wxaapi/newtmpl/addtemplate?access_token=ACCESS_TOKEN" 's response
    """
    postData = {}

    postData['touser'] = rsv.guest
    postData['template_id'] = SUBSC_TPL_ID
    postData['lang'] = "zh_CN"
    # postData['page'] = "pages/index/index" # 跳转页面

    rsverID = rsv.guest # 用户的openID
    rsver = (
        db.session.query("user")
        .fliter(User.openid == rsverID)
        .first().name
    )   # 用户的姓名
    
    itemID = rsv.itemId
    rsvItem = Item.queryItemName(itemId=itemID) # 预约物品名字

    rsvMeth = rsv.method
    rsvMethod = []
    if rsvMeth & 0b01:
        rsvMethod.append("时间段预约")
    if rsvMeth & 0b10:
        rsvMethod.append("灵活预约")
    rsvMethod = ",".join(rsvMethod)    

    rsvStt = rsv.state
    rsvSttDict: dict[int, str] = {
        RsvState.STATE_WAIT: "预约在等待审核",
        RsvState.STATE_START: "预约已开始",
        RsvState.STATE_COMPLETE: "预约已结束",
        RsvState.STATE_CANCEL: "预约已取消",
        RsvState.STATE_REJECT: "预约已被拒绝",
        RsvState.STATE_VIOLATE: "预约出现违规",
        RsvState.COMPLETE_BY_CANCEL: "预约被取消，已结束",
        RsvState.COMPLETE_BY_VIOLATE: "预约出现违规，已结束",
        RsvState.COMPLETE_BY_REJECT: "预约被拒绝，已结束"
    }
    rsvState = rsvSttDict[rsvStt]

    rsvReason = rsv.reason
    
    postData['data'] = {
        "name1":{
            "value": rsver
        },  # 预约者姓名

        "thing13":{
            "value": rsvItem
        },  # 预约项目

        "thing28":{
            "value": rsvMethod
        },  # 预约类型

        "phrase14":{
            "value": rsvState
        },  # 预约状态

        "thing7":{
            "value": rsvReason
        }   # 预约备注
    }

    accessToken = _ATManager(WX_APP_ID, WX_APP_SECRET).getAccessToken()   # 获取accessToken
    postData = json.dumps(postData)
    rqHeaders = {'Content-Type': 'application/json'}
    url = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token=%s" % accessToken
    res = requests.post(url, headers=rqHeaders, data=postData)

    return res

    
