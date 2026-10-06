"""Deterministic evidence. Gemini cannot rewrite source numbers or infer cohorts."""
import math
from datetime import date

VERSION="analysis-v1"
LABELS={"transparency":"Công khai, minh bạch","dvc-progress-tree":"Tiến độ giải quyết",
    "provide-online-tree":"Dịch vụ công trực tuyến","dossier-digitized":"Số hóa hồ sơ",
    "handling-satisfaction":"Mức độ hài lòng","formality-online-payment-tree":"Thanh toán trực tuyến"}
ACTIONS={"transparency":"Rà soát công bố, công khai và đồng bộ TTHC đúng hạn.",
    "dvc-progress-tree":"Rà soát hồ sơ quá hạn, phân công xử lý và theo dõi hồ sơ gần hạn.",
    "provide-online-tree":"Đối chiếu các chỉ tiêu thành phần để xác định khâu cung cấp hoặc sử dụng dịch vụ trực tuyến cần cải thiện.",
    "dossier-digitized":"Đảm bảo số hóa đầy đủ thành phần đầu vào; kiểm tra số hóa kết quả của hồ sơ đã hoàn thành. Hồ sơ đang trong hạn chưa có kết quả không được kết luận là thiếu số hóa kết quả.",
    "handling-satisfaction":"Rà soát hồ sơ quá hạn và các đánh giá không hài lòng, kể cả hồ sơ đúng hạn; không cộng trùng khi đối chiếu công thức.",
    "formality-online-payment-tree":"Kiểm tra hồ sơ có nghĩa vụ tài chính đã đến bước thanh toán và dữ liệu đồng bộ. Không kết luận hồ sơ chưa đến bước thanh toán là sai sót."}

def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):return None
    return value

def findings(groups,days=()):
    cards=[]
    def add(key,group,kind,title,evidence,action):
        cards.append(dict(id=key,groupId=group,kind=kind,title=title,evidence=evidence,action=action))
    for group in groups:
        key=group["id"];score=number(group.get("score"));maximum=number(group.get("maximum"))
        if key not in LABELS:continue
        params=group.get("parameters",{})
        if key=="dvc-progress-tree":
            received=number(params.get("totalReceived"));ontime=number(params.get("totalOnTime"));overdue=number(params.get("totalOverdue"))
            if received is not None and ontime is not None:
                if min(received,ontime)<0 or ontime>received:raise ValueError("Số hồ sơ không hợp lệ")
                if overdue is None:overdue=received-ontime
                if overdue<0 or received!=ontime+overdue:raise ValueError("Tổng tiếp nhận không bằng hồ sơ đúng hạn cộng quá hạn")
                if overdue>0:
                    add("overdue",key,"priority","Hồ sơ quá hạn ảnh hưởng đến tiến độ và hài lòng",
                        f"{overdue:g}/{received:g} hồ sơ đã và đang giải quyết quá hạn ({overdue/received*100:.2f}%).",
                        ACTIONS[key]+" Đối chiếu đồng thời ảnh hưởng đến chỉ tiêu hài lòng; không ước tính điểm mất khi thiếu công thức thành phần.")
        if score is None or maximum is None or maximum<=0:continue
        if score/maximum>=.95:
            add(key+":strong",key,"strength",LABELS[key]+" đạt gần mức điểm tối đa",
                f"{score:.2f}/{maximum:.2f} điểm trong kỳ đang chọn; chưa khẳng định ổn định nếu thiếu lịch sử.",
                "Duy trì quy trình hiện tại và kiểm tra tính đầy đủ của dữ liệu đồng bộ.")
        elif score/maximum<.8:
            add(key+":low",key,"priority",LABELS[key]+" còn dư địa cải thiện",
                f"{score:.2f}/{maximum:.2f} điểm. Đây là dấu hiệu cần đối chiếu, không phải kết luận nguyên nhân.",ACTIONS[key])
        for metric in group.get("metrics",[]):
            numerator=number(metric.get("numerator"));denominator=number(metric.get("denominator"))
            points=number(metric.get("score"));limit=number(metric.get("maximum"))
            if denominator is None or denominator<=3 or numerator is None or limit is None or limit<=0 or points is None:continue
            if points/limit<.8:
                add(key+":"+metric["code"],key,"priority","Cần rà soát: "+metric["name"],
                    f"{numerator:g}/{denominator:g}; {points:.2f}/{limit:.2f} điểm.",ACTIONS[key])
    # Three consecutive real reporting dates; never bridge gaps or changed maxima.
    recent=sorted(days,key=lambda item:item["reportDate"])[-3:]
    if len(recent)==3 and all((date.fromisoformat(recent[i+1]["reportDate"])-date.fromisoformat(recent[i]["reportDate"])).days==1 for i in (0,1)):
        for key in LABELS:
            observations=[d.get("groups",{}).get(key,{}) for d in recent]
            values=[number(g.get("score")) for g in observations]
            maxima=[g.get("maximum") for g in observations]
            if None not in values and maxima[0] is not None and len(set(maxima))==1 and all(values[i]-values[i+1]>=.05 for i in (0,1)):
                add(key+":decline",key,"priority",LABELS[key]+" giảm hai ngày liên tiếp",
                    "; ".join(f"{d['reportDate']}: {v:.2f} điểm" for d,v in zip(recent,values))+". Biến động ngày mang tính tham khảo; cần kiểm tra thay đổi công thức nguồn.",ACTIONS[key])
    # Keep a bounded output, prioritize overdue and verified daily trends before gaps.
    cards.sort(key=lambda c:(c["kind"]!="priority",c["id"]!="overdue",not c["id"].endswith(":decline")))
    return cards[:18]
