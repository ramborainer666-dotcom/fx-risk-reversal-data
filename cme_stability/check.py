#!/usr/bin/env python3
"""Read-only CME EURUSD VOI JSON connectivity audit for GitHub Actions.
Only summary metadata is stored; full CME option chains are NOT committed.
Undocumented website API: reliability not guaranteed. No login/cookies/bypass.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
HISTORY_PATH = ROOT / 'history.json'
SUMMARY_PATH = ROOT / 'summary.json'
ENDPOINT = 'https://www.cmegroup.com/CmeWS/mvc/Volume/Options/Details'
PRODUCT = '8116'
EXPIRY = 'Z26'
GROUPS = {'DEC-2026-Calls': 'Call', 'DEC-2026-Puts': 'Put'}
REFERENCE = {'DEC-2026-Calls': (68378,1546), 'DEC-2026-Puts': (70135,8542)}
MAX_BYTES = 8 * 1024 * 1024


def integer(value):
    if value is None or isinstance(value,bool):
        raise ValueError('Zahlenfeld fehlt oder falscher Typ')
    s = str(value).strip().replace(',','').replace(' ','')
    if s in ('----','-',''):
        return 0
    if not s.isdigit():
        raise ValueError('ungueltiger Integer')
    return int(s)


def target_date(day):
    day -= dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day.strftime('%Y%m%d')


def validate(payload, date):
    if not isinstance(payload,dict) or not isinstance(payload.get('monthData'),list):
        raise ValueError('monthData fehlt')
    groups = payload['monthData']
    if sorted(g.get('monthID') for g in groups if isinstance(g,dict)) != sorted(GROUPS):
        raise ValueError('falsche oder leere Monats-/Call-Put-Gruppen')
    if len(groups) != 2:
        raise ValueError('Anzahl Gruppen nicht 2')
    summary={}
    for group in groups:
        ident=group['monthID']
        rows=group.get('strikeData')
        total=group.get('totalData')
        if not isinstance(rows,list) or not rows or not isinstance(total,dict):
            raise ValueError('Strike- oder Summendaten fehlen')
        strikes=set(); oi_sum=vol_sum=0
        for row in rows:
            if not isinstance(row,dict): raise ValueError('ungueltige Strike-Zeile')
            s=str(row.get('strike','')).strip()
            if not s or not re.fullmatch(r'\d+(?:\.\d+)?',s):
                raise ValueError('ungueltiger Strike')
            if s in strikes: raise ValueError(f'doppelter Strike {s}')
            strikes.add(s)
            oi_sum+=integer(row.get('atClose'))
            vol_sum+=integer(row.get('totalVolume'))
        oi=integer(total.get('atClose'))
        vol=integer(total.get('totalVolume'))
        if (oi,vol)!=(oi_sum,vol_sum):
            raise ValueError('OI-/Volumensummen stimmen nicht')
        if date=='20261113' and (oi,vol)!=REFERENCE[ident]:
            raise ValueError('XLS-Referenz vom 13.11.2026 weicht ab')
        summary[GROUPS[ident]]={'strikes':len(rows),'oi':oi,'volume':vol}
    return summary


def obtain(date):
    params={'productid':PRODUCT,'tradedate':date,'expirationcode':EXPIRY,'reporttype':'P'}
    url=ENDPOINT+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={
        'Accept':'application/json','User-Agent':'QuikStrike-VOI-Stabilitaet/1.0'})
    with urllib.request.urlopen(req,timeout=35) as res:
        status=res.status
        ctype=res.headers.get('Content-Type','')
        raw=res.read(MAX_BYTES+1)
    if status!=200 or 'json' not in ctype.lower() or len(raw)>MAX_BYTES:
        raise ValueError(f'HTTP={status}, ContentType={ctype}, Bytes={len(raw)}')
    payload=json.loads(raw)
    details=validate(payload,date)
    return {'http':status,'sha256':hashlib.sha256(raw).hexdigest(),'groups':details,
            'request_url':url}


def load_history():
    if not HISTORY_PATH.exists(): return []
    history=json.loads(HISTORY_PATH.read_text(encoding='utf-8'))
    if not isinstance(history,list): raise ValueError('ungueltiges Protokoll')
    return history


def update_summary(history, last):
    passed=sorted({r['date'] for r in history if r.get('status')=='OK'})
    summary={'goal':5,'verified_distinct_days':len(passed),'successful_dates':passed,
             'goal_reached':len(passed)>=5,'last_check':last,
             'note':'Read-only test; no trading data imported, website API is undocumented.'}
    SUMMARY_PATH.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return summary


def run(date,force=False):
    history=load_history()
    successes={r['date'] for r in history if r.get('status')=='OK'}
    if len(successes)>=5 and not force:
        (ROOT / 'run_status.tmp').write_text('SKIPPED',encoding='utf-8')
        print(f'Fuenf verschiedene erfolgreiche Handelstage erreicht ({len(successes)}). Kein weiterer CME-Aufruf.')
        return True
    if date in successes and not force:
        (ROOT / 'run_status.tmp').write_text('SKIPPED',encoding='utf-8')
        print('Handelstag bereits erfolgreich geprueft: '+date+'; kein weiterer Abruf.')
        return True
    result={'date':date,'checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'status':'ERROR','product':'EURUSD','expiration':'Z26','reporttype':'P'}
    try:
        result.update(obtain(date))
        result['status']='OK'
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError,
            OSError,TypeError,json.JSONDecodeError) as ex:
        result['error']=f'{type(ex).__name__}: {str(ex)[:180]}'
    history.append(result)
    history=history[-120:]
    HISTORY_PATH.write_text(json.dumps(history,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    summary=update_summary(history,result)
    (ROOT / 'run_status.tmp').write_text(result['status'],encoding='utf-8')
    print('EURUSD CME JSON',date,result['status'])
    if result['status']=='OK':
        for side,v in result['groups'].items():
            print(f'{side}: Strikes {v["strikes"]}, OI {v["oi"]}, Volume {v["volume"]}')
    else:
        print(result['error'])
    print('Unterschiedliche erfolgreiche Handelstage:',summary['verified_distinct_days'],'/ 5')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write(f'## CME EURUSD EOD – {date}\n\nStatus: **{result["status"]}**  \n')
            f.write(f'Erfolgreiche verschiedene Tage: **{summary["verified_distinct_days"]}/5**\n')
            if result.get('error'): f.write(f'\nFehler: \`{result["error"]}\`\n')
    return result['status']=='OK'


def selftest():
    data={'monthData':[
        {'monthID':'DEC-2026-Calls','totalData':{'atClose':'68,378','totalVolume':'1,546'},'strikeData':[{'strike':'1.1000','atClose':'68,378','totalVolume':'1,546'}]},
        {'monthID':'DEC-2026-Puts','totalData':{'atClose':'70,135','totalVolume':'8,542'},'strikeData':[{'strike':'1.1000','atClose':'70,135','totalVolume':'8,542'}]}
    ]}
    assert validate(data,'20261113')['Call']['oi']==68378
    assert validate(data,'20261112')['Put']['volume']==8542
    assert target_date(dt.date(2026,11,16))=='20261113'
    assert target_date(dt.date(2026,11,15))=='20261113'
    data['monthData'][0]['strikeData'].append(dict(data['monthData'][0]['strikeData'][0]))
    try:validate(data,'20261112'); raise AssertionError('Duplicate not caught')
    except ValueError:pass
    data['monthData'][0]['strikeData'].pop()
    data['monthData'][0]['totalData']['totalVolume']='2'
    try:validate(data,'20261112'); raise AssertionError('Sum mismatch not caught')
    except ValueError:pass
    assert integer('1,234')==1234
    print('7 lokale Tests bestanden. Kein CME-Abruf.')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--date',help='optional YYYYMMDD; Standard: letzter Werktag in Berlin')
    p.add_argument('--selftest',action='store_true')
    p.add_argument('--force',action='store_true')
    a=p.parse_args()
    if a.selftest:
        selftest()
    else:
        today=dt.datetime.now(ZoneInfo('Europe/Berlin')).date()
        date=a.date or target_date(today)
        if not re.fullmatch(r'\d{8}',date): p.error('Datum YYYYMMDD')
        dt.datetime.strptime(date,'%Y%m%d')
        run(date,force=a.force)
