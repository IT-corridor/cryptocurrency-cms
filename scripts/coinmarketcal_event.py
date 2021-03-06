import json
import time
import requests
import datetime
import urllib2
from lxml import etree

import os
from os import sys, path
import django
import pdb

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qobit_cms.settings")
django.setup()

from general.models import *
from general.utils import *
from utils import send_email

CLIENT_ID = '917_4rbbdcjtwuqsskoo8goow88088wkg0w0cscgs08s488w84s40w'
CLIENT_SECRET = '4vd1mse6sg00wg484scskssskswk0s800ksw0so804k4o8gss0'

def main():
    url = 'https://api.coinmarketcal.com/oauth/v2/token?grant_type=client_credentials&client_id={}&client_secret={}'.format(CLIENT_ID, CLIENT_SECRET)
    access_token = requests.get(url).json()['access_token']

    # get categories
    url = 'https://api.coinmarketcal.com/v1/categories?access_token={}'.format(access_token)
    info = requests.get(url).json()

    for ii in info:
        CoinmarketcalCategory.objects.update_or_create(uid=ii['id'], defaults={ 'name': ii['name'] })
        
    # get events
    page = 1
    max_page = 10
    last_created_at = CoinmarketcalEvent.objects.all().order_by('-created_date').first()
    last_created_at = last_created_at.created_date.replace(tzinfo=None) if last_created_at else datetime.datetime(2016, 12, 12)

    while page < max_page:
        url = 'https://api.coinmarketcal.com/v1/events?access_token={}&page={}&max=150&dateRangeStart=22%2F12%2F2016&sortBy=created_desc&showMetadata=true'.format(access_token, page)
        info = requests.get(url).json()
        max_page = info['_metadata']['page_count']
        page += 1

        for ii in info['records']:
            ii['uid'] = ii.pop('id')
            ii['coins'] = ', '.join([iii['id'] for iii in ii['coins']])
            categories = ii['categories']
            ii['categories'] = ', '.join([str(iii['id']) for iii in ii['categories']])
            ii['date_event'] = datetime.datetime.strptime(ii['date_event'][:-6], '%Y-%m-%dT%H:%M:%S')
            ii['created_date'] = datetime.datetime.strptime(ii['created_date'][:-6], '%Y-%m-%dT%H:%M:%S')
            item = CoinmarketcalEvent(**ii)
            print (ii)

            if item.created_date > last_created_at:
                item.save()
                ii.pop('uid')
                ii.pop('categories')
                ii['date_event_start'] = ii.pop('date_event')
                ii['cml_coins'] = ii.pop('coins')
                ii['description'] = (ii['description'] or '').strip('"')

                ii['cml_id'] = item.id
                ii['culture_id'] = 1
                # to get real source
                if ii['source'].find('coinmarketcal.com') > -1:
                    response = urllib2.urlopen(ii['source'])
                    htmlparser = etree.HTMLParser()
                    tree = etree.parse(response, htmlparser)
                    xpath = '//*[@id="event-detail"]/div[4]/div[1]/div[1]/div[3]/a[2]/@href'
                    ii['source'] = tree.xpath(xpath)[0]
                ce = CoinEvent.objects.create(**ii)
                # add categories
                for category in categories:
                    cc = CoinEventCategory.objects.filter(name=category['name']).first()
                    if cc:
                        ce.categories.add(cc)
                # add coins
                flag = False
                for coin in ii['cml_coins'].split(', '):
                    co = CoinmarketcalCoin.objects.filter(uid=coin).first()
                    if co:
                        mc = MasterCoin.objects.filter(coinmarketcal=co.id).first()
                        if mc:
                            ce.coins.add(mc)
                            flag = True
                if not flag:
                    ce.status = 'draft'
                    ce.save()

                CoinEventLocale.objects.create(event=ce, culture_id=2, title=translate(ii['title']), description=ii['description'])
            else:
                return


if __name__ == "__main__":
    main()
