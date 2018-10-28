from requests import Request, Session
import argparse
import json
import os.path


def login(username, password):
    assert username is not None
    assert password is not None

    print("Trying to login as: ", username)
    login_url = "https://sso.garmin.com/sso/signin?service=https%3A%2F%2Fconnect.garmin.com%2Fmodern%2F&webhost=https%3A%2F%2Fconnect.garmin.com&source=https%3A%2F%2Fconnect.garmin.com%2Fen-US%2Fsignin&redirectAfterAccountLoginUrl=https%3A%2F%2Fconnect.garmin.com%2Fmodern%2F&redirectAfterAccountCreationUrl=https%3A%2F%2Fconnect.garmin.com%2Fmodern%2F&gauthHost=https%3A%2F%2Fsso.garmin.com%2Fsso&locale=en_US&id=gauth-widget&cssUrl=https%3A%2F%2Fstatic.garmincdn.com%2Fcom.garmin.connect%2Fui%2Fcss%2Fgauth-custom-v1.2-min.css&privacyStatementUrl=%2F%2Fconnect.garmin.com%2Fen-US%2Fprivacy%2F&clientId=GarminConnect&rememberMeShown=true&rememberMeChecked=true&createAccountShown=true&openCreateAccount=false&displayNameShown=false&consumeServiceTicket=false&initialFocus=true&embedWidget=false&generateExtraServiceTicket=true&generateNoServiceTicket=false&globalOptInShown=true&globalOptInChecked=false&mobile=false&connectLegalTerms=true&locationPromptShown=true"
    login_data = {"username": username, "password": password}
    s = Session()
    s.headers["user-agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36"

    login_request = Request(method="POST", url=login_url, data=login_data)
    resp = s.send(request=login_request.prepare())
    assert resp.status_code == 200

    if any(cookie.name == 'CASTGC' for cookie in s.cookies):
        print("Credentials OK")
    else:
        print("Bad Credentials")
        return False, None

    # Make another call to complete the auth process
    resp = s.get(url="https://connect.garmin.com/modern/")
    assert resp.status_code == 200
    print("Connected!")
    return True, s


def get_activities(session, limit, clean_empty_vals=False):
    get_activity_collection_url = "https://connect.garmin.com/modern/proxy/activitylist-service/activities/search/activities?limit={0}&start=0".format(limit)
    resp = session.get(url=get_activity_collection_url)
    if resp.status_code == 200:
        if clean_empty_vals:
            activities = list()
            for activity in resp.json():
                activities.append({k: v for k, v in activity.items() if v is not None or k  in ("activityId", "activityName")})
            return activities
        else:
            return resp.json()
    else:
        print("Failed to get activity collection")
        return None


def get_activity_details(session, id):
    url_to_result_property_names = {
        "https://connect.garmin.com/modern/proxy/activity-service/activity/{0}".format(id) : "overview",
        "https://connect.garmin.com/modern/proxy/activity-service/activity/{0}/splits".format(id) : "splits",
        "https://connect.garmin.com/modern/proxy/activity-service/activity/{0}/details?maxChartSize=2000&maxPolylineSize=4000".format(id) : "details",
        "https://connect.garmin.com/modern/proxy/weather-service/weather/{0}".format(id) : "weather"
    }

    result = {}
    for url, property_name in url_to_result_property_names.items():
        resp = session.get(url=url)
        if resp.status_code != 200:
            print("Failed to get", property_name, "data for activity", id)
            return None

        result[property_name] = resp.json()

    return result


parser = argparse.ArgumentParser()
parser.add_argument("username", help="The user name", type=str)
parser.add_argument("password", help="The password", type=str)
parser.add_argument("limit", help="The number of activities to download", type=int)
parser.add_argument("path", help="The output folder", type=str)
parser.add_argument("--redownload", help="whether to redownload existing activities", type=str)
args = parser.parse_args()

successful, session = login(args.username, args.password)

if not successful:
    exit(1)

activities = get_activities(session=session, limit=args.limit, clean_empty_vals=True)

print("Got", len(activities), "activities")
with open(args.path + "/activity_collection.json", "w") as outfile:
    json.dump(activities, outfile, indent=4)

i=0
activity_count=len(activities)
for activity in activities:
    i+=1
    if activity["activityId"] is None:
        print("Skipping activity without id")
        continue

    print(i, "/", activity_count, "Downloading activity details:", activity["activityId"], activity["activityName"], activity["startTimeLocal"])

    path = args.path + "/" + str(activity["activityId"]) + ".json"
    if not os.path.exists(path) or args.redownload:
        activity_details = get_activity_details(session=session, id=activity["activityId"])
        with open(args.path + "/" + str(activity["activityId"]) + ".json", "w") as outfile:
            json.dump(activity_details, outfile, indent=4)

exit(0)
