import json
import time
import requests
import datetime
import urllib2
from lxml import etree

import os
from os import sys, path
import django

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qobit_cms.settings")
django.setup()

from general.models import *
import pdb

def get_csv(str1, list2):
    list_val = (str1 or '').split(',') + list2
    list_val = [ii for ii in list_val if ii and ii.strip()]
    return ','.join(set(list_val))

def get_identifier(list1, list2):
    result = []
    for ii in list1:
        if not ii:
            continue
        for iii in list2:
            if iii in ii:
                result.append(ii.split(iii)[1].strip('/'))
    return result

def clean_text(text):
    try:
        return int(text.strip().replace(',', ''))
    except Exception as e:
        pass

def main():
    current_time = datetime.datetime.now()
    for coin in MasterCoin.objects.all():
        hour_info = {}
        locale_info = {}

        print (coin.id, coin.symbol, '----------------')
        if coin.cryptocompare:
            cc_coin = CryptocompareCoin.objects.get(id=coin.cryptocompare)
            url_ = 'https://www.cryptocompare.com/api/data/coinsnapshotfullbyid/?id={}'.format(cc_coin.uid)
            info = requests.get(url_).json()['Data']['General']

            coin.launch_date = datetime.datetime.strptime(info['StartDate'], '%d/%m/%Y') if info.get('StartDate') and info.get('StartDate') != '01/01/0001' else None
            coin.algorithm = info.get('Algorithm')
            coin.proof_type = info.get('ProofType')
            coin.links_website = get_csv(coin.links_website, [info.get('WebsiteUrl')])
            coin.social_twitter_identifier = get_csv(coin.social_twitter_identifier, [info.get('Twitter')])

            total_supply = info.get('TotalCoinSupply') or None
            if total_supply and total_supply.count('.') > 1:
                total_supply = total_supply.replace('.', '')
                
            hour_info = {
                'total_supply': total_supply,
                'net_hashes_per_second': info.get('NetHashesPerSecond') or None,
                'block_number': info.get('BlockNumber') or None,
                'block_reward_reduction': info.get('BlockRewardReduction') or None,
                'difficulty_adjustment': info.get('DifficultyAdjustment') or None,
                'block_time': info.get('BlockTime') or None,
                'block_reward': info.get('BlockReward') or None
            }

            locale_info = {
                'description': info.get('Description'),
                'feature': info.get('Features'),
                'technology': info.get('Technology')
            }

        if coin.coingecko:
            cg_coin = CoingeckoCoin.objects.get(id=coin.coingecko)
            url_ = 'https://api.coingecko.com/api/v3/coins/{}'.format(cg_coin.uid)
            info = requests.get(url_).json()

            coin.coingecko_category = get_csv('', info.get('categories'))
            coin.ico_data = json.dumps(info.get('ico_data', {}))
            
            coin.chat_telegram_identifier = get_csv(coin.chat_telegram_identifier, [info.get('links')['telegram_channel_identifier']])
            coin.chat_discord_identifier = get_csv(coin.chat_discord_identifier, get_identifier(info.get('links').get('chat_url', []), ['discord.gg', 'discordapp.com/invite']))
            coin.chat_slack_identifier = get_csv(coin.chat_slack_identifier, [info.get('ico_data', {}).get('links', {}).get('slack')])

            # coin.social_reddit_identifier = get_csv(coin.social_reddit_identifier, info.get('WebsiteUrl'))
            coin.social_twitter_identifier = get_csv(coin.social_twitter_identifier, [info.get('links')['twitter_screen_name']])
            coin.social_facebook_identifier = info.get('links')['facebook_username']
            coin.social_btt_identifier = info.get('links')['bitcointalk_thread_identifier']
            
            coin.links_website = get_csv(coin.links_website, info.get('links')['homepage'])
            coin.links_whitepaper = get_csv(coin.links_whitepaper, [info.get('ico_data', {}).get('links', {}).get('whitepaper')])
            coin.links_ann = get_csv(coin.links_ann, info.get('links')['announcement_url'])
            coin.links_explorer = get_csv(coin.links_explorer, info.get('links')['blockchain_site'])
            coin.links_source_code = get_csv(coin.links_source_code, [info.get('ico_data', {}).get('links', {}).get('github')])
            coin.links_forum = get_csv(coin.links_forum, info.get('links')['official_forum_url'])
            coin.links_blog = get_csv(coin.links_blog, [info.get('ico_data', {}).get('links', {}).get('blog')])

            hour_info['circulating_supply'] = info.get('market_data').get('circulating_supply')
            hour_info['facebook_likes'] = info.get('community_data')['facebook_likes']
            hour_info['twitter_followers'] = info.get('community_data')['twitter_followers']
            hour_info['reddit_subscribers'] = info.get('community_data')['reddit_subscribers']
            hour_info['reddit_average_posts_48h'] = info.get('community_data')['reddit_average_posts_48h']
            hour_info['reddit_average_comments_48h'] = info.get('community_data')['reddit_average_comments_48h']
            hour_info['reddit_accounts_active_48h'] = info.get('community_data')['reddit_accounts_active_48h']

            hour_info['repo_forks'] = info.get('developer_data')['forks']
            hour_info['repo_stars'] = info.get('developer_data')['stars']
            hour_info['repo_subscribers'] = info.get('developer_data')['subscribers']
            hour_info['repo_total_issues'] = info.get('developer_data')['total_issues']
            hour_info['repo_closed_issues'] = info.get('developer_data')['closed_issues']
            hour_info['repo_pull_requests_merged'] = info.get('developer_data')['pull_requests_merged']
            hour_info['repo_pull_request_contributors'] = info.get('developer_data')['pull_request_contributors']
            hour_info['repo_commit_count_4_weeks'] = info.get('developer_data')['commit_count_4_weeks']
            hour_info['alexa_rank'] = info.get('public_interest_stats')['alexa_rank']
            hour_info['bing_matches'] = info.get('public_interest_stats')['bing_matches']

        coin.save()

        if coin.coinmarketcap:
            cmc_coin = CoinmarketcapCoin.objects.get(id=coin.coinmarketcap)
            try:
                url_ = 'https://coinmarketcap.com/currencies/{}/'.format(cmc_coin.token)
                response = urllib2.urlopen(url_)
                htmlparser = etree.HTMLParser()
                tree = etree.parse(response, htmlparser)
                total_supply = tree.xpath("/html/body/div[@class='container main-section']/div[@class='row']/div[@class='col-lg-10']/div[@class='row bottom-margin-2x']/div[@class='col-sm-8 col-sm-push-4']/div[@class='coin-summary-item col-xs-6 col-md-3'][4]/div[@class='coin-summary-item-detail details-text-medium']/span/text()")
                hour_info['total_supply'] = clean_text(total_supply[0]) if total_supply else None
                circulating_supply = tree.xpath("/html/body/div[@class='container main-section']/div[@class='row']/div[@class='col-lg-10']/div[@class='row bottom-margin-2x']/div[@class='col-sm-8 col-sm-push-4']/div[@class='coin-summary-item col-xs-6 col-md-3'][3]/div[@class='coin-summary-item-detail details-text-medium']/span/text()")
                hour_info['circulating_supply'] = clean_text(circulating_supply[0]) if circulating_supply else None
            except Exception as e:
                print str(e)

        if hour_info:
            print (hour_info)
            hour_info['coin_id'] = coin.id
            hour_info['date_of_entry'] = current_time
            CoinHourlyInfo.objects.create(**hour_info)

        if locale_info:
            culture = Culture.objects.filter(name='en_US').first()
            CoinLocale.objects.update_or_create(coin=coin, culture=culture, defaults=locale_info)


if __name__ == "__main__":
    main()
