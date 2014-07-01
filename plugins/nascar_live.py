# nascar_live.py plugin by craisins

import json
import re
import time
from bs4 import BeautifulSoup

from urllib2 import HTTPError

from util import hook, http


messages = []
#current_race_id = -1

nascar = {
    "crond_interval": 60,
    "leaderboard_live_url": "http://www.nascar.com/en_us/sprint-cup-series/leaderboard/leaderboard-live.html",
    "leaderboard_json_re": r'(/leaderboard/Series_[0-9]/[0-9]{4}/[0-9]*/[0-9]/leaderboard.json)',
    "current_race_id": -1
}

@hook.command("next")
def next(inp, db=None):
    result = db.execute("select * from nascar_raceschedule where timestamp > ?", (time.time(),)).fetchone()
    if result:
        return u"\x02{}\x02 at \x02{}\x02 ({}, {})".format(result[2], result[3], time.strftime("%a, %b %d @ %I:%M%p ET", time.localtime(result[1])), result[4])
    else:
        return u"No upcoming races found."

@hook.command("race")
def race(inp, db=None):
    if nascar['current_race_id'] == -1:
        return "No active race."
    result = db.execute("select * from nascar_races where RaceID = ?", (nascar['current_race_id'],)).fetchone()
    if result:
        return "\x02{}\x02 at \x02{}\x02 ({}mi), \x02Laps:\x02 {}/{}, \x02Weather:\x02 {}".format(result[4], result[7], result[8], result[10], result[12], result[19])


@hook.command("leader")
def leader(inp, db=None):
    race_id = nascar['current_race_id']
    result = get_current_leader(race_id, db)
    if result:
        return "\x02[LEADER]\x02 #{} {}".format(result[0], result[1])


@hook.command("standings")
def standings(inp, db=None):
    if inp.strip() == "":
        result = db.execute("select * from nascar_standings where rank <= 5 and rank != -1 order by rank asc").fetchall()
        output = ""
        for r in result:
            output = output + u"\x02{}.\x02 {} {} ({} pts). ".format(ordinal(r[4]), r[1], r[2], r[5])
        return output
    try:
        result = None
        inp = int(inp)
    except ValueError:
        result = db.execute("select * from nascar_standings where replace(lower(last_name),'.','') like ? "
            " or lower(replace(first_name,'.','')) || lower(replace(last_name,'.','')) = ?", (inp.lower(), inp.replace('.','').replace(' ','').lower())).fetchone()
    if result is None:
        result = db.execute("select * from nascar_standings where driver_no = ?", (inp,)).fetchone()

    if not result or result[3] == -1:
        return u"No driver stats found."

    return u"\x02#{} {} {}\x02 is ranked {} with {} points.".format(result[3], result[1], result[2], ordinal(result[4]), result[5])


@hook.command("position")
def position(inp, db=None):
    try:
        result = None
        inp = int(inp)
    except ValueError:
        result = db.execute("select * from nascar_racestats where RaceID = ? and (lower(LastName) like ? or lower(FirstName) || ' ' || lower(LastName) like ?);", (nascar['current_race_id'], inp.lower(), inp.lower())).fetchone()
    if result is None:
        result = db.execute("select * from nascar_racestats where RaceID = ? and CarNo = ?;", (nascar['current_race_id'], inp)).fetchone()
    
    if not result:
        return "No race results found."

    driver_name = result[28] + " " + result[29]
    driver_carno = result[10]
    driver_pos = result[18]
    driver_sponsor = result[21]
    driver_behindleader = result[24]
    driver_ontrack = result[35]

    if driver_pos == 1:
        get_position = 2
    else:
        get_position = driver_pos - 1

    other_driver = db.execute("select * from nascar_racestats where RaceID = ? and RaceRank = ?", (nascar['current_race_id'], get_position)).fetchone()
    other_driver_name = other_driver[28] + " " + other_driver[29]
    other_driver_carno = other_driver[10]
    other_driver_pos = other_driver[18]
    other_driver_behindleader = other_driver[24]

    if driver_pos == 1:
        return "\x02#{} {}\x02: {}. {}s ahead of #\x02{} {}\x02 in {}.".format(driver_carno, driver_name, ordinal(driver_pos), abs(other_driver_behindleader), other_driver_carno, other_driver_name, ordinal(other_driver_pos))
    #if driver_ontrack == 0:
    #    return "\x02#{} {}\x02: {}. Currently off-track.".format(driver_carno, driver_name, ordinal(driver_pos))

    return "\x02#{} {}\x02: {}. {}s behind #\x02{} {}\x02 in {}.".format(driver_carno, driver_name, ordinal(driver_pos), abs(driver_behindleader - other_driver_behindleader), other_driver_carno, other_driver_name, ordinal(other_driver_pos))


def get_active_json_url(db=None):
    try:
        page = http.get(nascar['leaderboard_live_url'])
    except HTTPError:
        print "Can't get leaderboard live URL"
        return ""

    json_url_matches = re.search(nascar['leaderboard_json_re'], page)
    if json_url_matches.group(0):
        return "http://www.nascar.com" + json_url_matches.group(0)
    else:
        return ""


def parse_standings(db=None):
    url = "http://www.nascar.com/en_us/sprint-cup-series/drivers.html"
    try:
        page = http.get(url)
    except HTTPError:
        print "Can't get standings."
        return ""

    soup = BeautifulSoup(page)
    drivers = soup.find_all('article', class_='driverCard')
    for driver in drivers:
        data = {
            'first_name': '',
            'last_name': '',
            'driver_no': -1,
            'rank': -1,
            'points': -1
        }
        if 'data-first-name' in driver.attrs:
            data['first_name'] = driver.attrs['data-first-name']
        if 'data-last-name' in driver.attrs:
            data['last_name'] = driver.attrs['data-last-name']
        if 'data-rank' in driver.attrs:
            data['rank'] = int(driver.attrs['data-rank'].replace('--', '-1'))
        if 'data-number' in driver.attrs:
            data['driver_no'] = driver.attrs['data-number']
            if data['driver_no'] == '':
                data['driver_no'] = -1
            else:
                data['driver_no'] = int(data['driver_no'])
        data['points'] = int(driver.find('dl', class_='points').find('dd').find(text=True).replace('--', '-1'))
        upsert_standings(db, data)

def parse_json(json_url, db=None):
    # check to see if it's a 404 page
    try:
        page = http.get(json_url)
    except HTTPError:
        print "Can't get live stats."
        return ""

    page_matches = re.search(r'404 Not Found', page)
    if page_matches is not None and page_matches.group(0):
        return False

    js = json.loads(page)
    raceinfo = js
    race_id = raceinfo['RaceID']
    print "HERE IS THE RACE_ID => {}".format(race_id)
    nascar['current_race_id'] = race_id
    raceinfo = clean_raceinfo(raceinfo)
    upsert_raceinfo(db, raceinfo)

    previous_leader = get_current_leader(race_id, db)
    passings = json.loads(page)
    passings = passings['Passings']
    for driver in passings:
        driver = clean_racestats(driver)
        upsert_racestats(race_id, db, driver)

    current_leader = get_current_leader(race_id, db)

    if current_leader != previous_leader:
        messages.append("\x02[NEW LEADER]\x02 #{} {}".format(str(current_leader[0]), current_leader[1]))

    print "parsed json"



def say_messages(say=None):
    while len(messages) > 0:
        say(messages.pop())
        time.sleep(10)


def get_current_leader(race_id, db=None):
    result = db.execute("select CarNo, FirstName || ' ' || LastName from nascar_racestats where RaceID = ? and RaceRank = ?", (race_id, 1)).fetchone()
    if result:
        return result


def should_we_parse_json(db=None):
    current_time = time.time()
    result = db.execute("select id from nascar_raceschedule where (timestamp - 30 * 60) < ? and ? < (timestamp + 5 * 60 * 60)", (current_time, current_time)).fetchone()
    if result:
        return True
    return False


@hook.event("JOIN")
@hook.singlethread
def nascar_live_crond(inp, db=None, say=None):
    create_tables(db)
    fill_schedule(db)
    json_url = get_active_json_url(db)
    parse_standings(db)
    while(True):
        print "nascar_live_crond"
        if should_we_parse_json(db):
            print "we should parse json"
            parse_json(json_url, db)
        else:
            nascar['current_race_id'] = -1
        say_messages(say)
        time.sleep(nascar['crond_interval'])


def fill_schedule(db=None):
    schedule_url = "http://espn.go.com/racing/schedule"
    page = http.open(schedule_url)
    soup = BeautifulSoup(page)
    table = soup.find('table', class_='tablehead')
    trs = table.find_all('tr')
    for tr in trs:
        if tr.attrs['class'][0] == "stathead" or tr.attrs['class'][0] == "colhead":
            continue
        tds = tr.find_all('td')
        timestamp_br = tds[0].find('br')
        timestamp_br.extract()
        timestamp = tds[0].contents
        timestamp = timestamp[0] + " " + timestamp[1]
        timestamp = timestamp.replace('&nbsp;', ' ').replace('Noon', '12:00 PM').replace(u'\xa0', ' ').replace(' ET', '') + ' 2014'
        timestamp = time.strptime(timestamp, "%a, %b %d %I:%M %p %Y")
        timestamp = time.mktime(timestamp)
        name = tds[1].find('b').find(text=True)
        name_b = tds[1].find('b')
        name_b.extract()
        speedway = tds[1].find(text=True).replace('<br>', '')
        network = tds[2].find(text=True)
        if network is None:
            if tds[2].find('a').attrs['href'] == "http://espn.go.com/espntv/onair/index":
                network = "ESPN"
            elif tds[2].find('a').attrs['href'] == "http://espn.go.com/abcsports/":
                network = "ABC"
        else:
            network = str(network).strip()

        data = {
            "timestamp": timestamp,
            "name": name,
            "speedway": speedway,
            "network": network
        }
        upsert_raceschedule(db, data)

########## utils ###########

def create_tables(db=None):
    tables = ['nascar_races', 'nascar_racestats', 'nascar_raceschedule', 'nascar_standings']
    for table in tables:
        fp = file('plugins/data/nascar_live/create_'+table+'.sql', 'r')
        query = fp.read()
        print "Created table: " + table
        fp.close()
        db.execute(query)
    db.commit()

ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(n/10%10!=1)*(n%10<4)*n%10::4])

def upsert_raceschedule(db=None, data={}):
    print data
    result = db.execute("select * from nascar_raceschedule where timestamp = ?", (data['timestamp'],)).fetchone()
    if result:
        timestamp = data['timestamp']
        del data['timestamp']
        sql = "update nascar_raceschedule set "
        sql_list = []
        for key, val in data.items():
            sql_list.append(key + " = ?")
        sql = sql + ", ".join(sql_list) + " where timestamp = ?;"
        sql_params = data.values()
        sql_params.append(timestamp)
        db.execute(sql, sql_params)
        db.commit()
    else:
        question_mark_list = []
        for i in range(0, len(data)):
            question_mark_list.append("?")
        sql = "insert into nascar_raceschedule("+",".join(data.keys())+") values("+",".join(question_mark_list)+");"
        sql_params = data.values()
        db.execute(sql, sql_params)
        db.commit()


def upsert_raceinfo(db=None, data={}):
    if data['RaceID'] is None:
        return
    race_id = data['RaceID']

    result = db.execute("select * from nascar_races where RaceID = ?", (race_id, )).fetchone()
    if result:
        del data['RaceID']
        sql = "update nascar_races set "
        sql_list = []
        for key, val in data.items():
            sql_list.append(key + " = ?")
        sql = sql + ", ".join(sql_list) + " where RaceID = ?;"
        sql_params = data.values()
        sql_params.append(race_id)
        db.execute(sql, sql_params)
        db.commit()
    else:
        question_mark_list = []
        for i in range(0, len(data)):
            question_mark_list.append("?")
        sql = "insert into nascar_races("+",".join(data.keys())+") values("+",".join(question_mark_list)+");"
        db.execute(sql, data.values())
        db.commit()


def upsert_racestats(race_id, db=None, data={}):
    if data['HistoricalID'] is None or race_id is None:
        return

    driver_id = data['HistoricalID']
    result = db.execute("select * from nascar_racestats where RaceID = ? and HistoricalID = ?", (race_id, driver_id)).fetchone()
    if result:
        del data['HistoricalID']
        sql = "update nascar_racestats set "
        sql_list = []
        for key, val in data.items():
            sql_list.append(key + " = ?")
        sql = sql + ", ".join(sql_list) + " where RaceID = ? and HistoricalID = ?;"
        sql_params = data.values()
        sql_params.append(race_id)
        sql_params.append(driver_id)
        db.execute(sql, sql_params)
        db.commit()
    else:
        question_mark_list = []
        for i in range(0, len(data)):
            question_mark_list.append("?")
        sql = "insert into nascar_racestats("+",".join(data.keys())+",RaceID) values("+",".join(question_mark_list)+",?);"
        sql_params = data.values()
        sql_params.append(race_id)
        db.execute(sql, sql_params)
        db.commit()


def upsert_standings(db=None, data={}):
    if data['first_name'] is None and data['last_name'] is None:
        return

    result = db.execute("select id from nascar_standings where lower(first_name) = ? and lower(last_name) = ?", (data['first_name'].lower(), data['last_name'].lower())).fetchone()
    if result:
        sql = "update nascar_standings set "
        sql_list = []
        for key, val in data.items():
            sql_list.append(key + " = ?")
        sql = sql + ", ".join(sql_list) + " where id = ?"
        sql_params = data.values()
        sql_params.append(result[0])
        db.execute(sql, sql_params)
        db.commit()
    else:
        question_mark_list = []
        for i in range(0, len(data)):
            question_mark_list.append("?")
        sql = "insert into nascar_standings("+",".join(data.keys())+") values("+",".join(question_mark_list)+");"
        sql_params = data.values()
        db.execute(sql, sql_params)
        db.commit()


def clean_racestats(data={}):
    del data['LapsLed']
    del data['Driver']
    return data

def clean_raceinfo(data={}):
    del data['Passings']
    data['Weather'] = str(data['weatherInfo']['temp_f']) + "F, " + data['weatherInfo']['weather']
    del data['weatherInfo']
    return data
