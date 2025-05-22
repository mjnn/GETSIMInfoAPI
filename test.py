from SIMDetailsGetter import *
from datetime import datetime

print(datetime.now())
sim_info_getter_GP = SIMInfoGetter('GP','LSVXBABDXR2023167')
sim_data = sim_info_getter_GP.get_sim_data()
if sim_data["success"] ==  True:
    print(json.dumps(sim_data,indent=4,ensure_ascii=False))
elif sim_data["success"] ==  False:
    if sim_data["error_message"] == "cookies_need_update":
        sim_info_getter_GP.update_cookies()
        sim_data=sim_info_getter_GP.get_sim_data()
        print(json.dumps(sim_data,indent=4,ensure_ascii=False))
    else:
        print(json.dumps(sim_data,indent=4,ensure_ascii=False))