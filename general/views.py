import os
import json
import requests
import datetime
import mimetypes

from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.http import HttpResponse, JsonResponse
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict

from django.utils.encoding import smart_str
from wsgiref.util import FileWrapper
from django.contrib.contenttypes.models import ContentType

from general.models import *


def user_login(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    else:
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse('home'))
        else:
            message = 'Your login credential is incorrect! Please try again.'
            return render(request, 'login.html', {
                'message': message,
            })


def user_logout(request):
    logout(request)
    return HttpResponseRedirect('/login') 


@login_required(login_url='/login')
def home(request):
    return render(request, 'index.html', {})


@login_required(login_url='/login')
def master_coins(request):
    return render(request, 'master_coins.html', {})


@login_required(login_url='/login')
def exchanges(request):
    return render(request, 'exchanges.html', {})


@login_required(login_url='/login')
def supported_exchanges(request):
    return render(request, 'supported_exchanges.html', {})


@login_required(login_url='/login')
def exchange_detail(request, id):
    exchange = Exchange.objects.get(id=id)
    return render(request, 'exchange_detail.html', { "exchange": exchange })


@login_required(login_url='/login')
def exchange_support(request, id):
    exchange = Exchange.objects.get(id=id)
    exchange.supported = True
    exchange.supported_at = datetime.datetime.now()
    exchange.save()
    return HttpResponseRedirect(reverse('exchange_detail', kwargs={ 'id': id }))

@login_required(login_url='/login')
def add_pair(request, exchange, pair):
    [base, quote] = pair.split('-')
    exchange = Exchange.objects.get(id=exchange)
    coins = MasterCoin.objects.all().order_by('symbol')

    cc_support = CryptocomparePair.objects.filter(Q(exchange__iexact=exchange.cryptocompare) &
                                                 (Q(base_coin=base) |
                                                  Q(quote_coin=quote))).exists()
    cp_support = CoinapiPair.objects.filter(Q(exchange__iexact=exchange.coinapi) &
                                             (Q(base_coin=base) |
                                              Q(quote_coin=quote))).exists()

    bd_coins = [ii.symbol for ii in MasterCoin.objects.filter(original_symbol=base)]
    bd_coins = ', '.join(bd_coins) if len(bd_coins) > 1 else ''
    qd_coins = [ii.symbol for ii in MasterCoin.objects.filter(original_symbol=quote)]
    qd_coins = ', '.join(qd_coins) if len(qd_coins) > 1 else ''

    if request.method == 'POST':
        base_coin = request.POST.get('base_coin')
        quote_coin = request.POST.get('quote_coin')
        
        pair = ExchangePair(exchange=exchange,
                            base_coin_id=base_coin,
                            quote_coin_id=quote_coin,
                            cryptocompare_availability=cc_support,
                            coinapi_availability=cp_support,
                            supported=True,
                            supported_at=datetime.datetime.now())
        pair.save()
        pair_supported = True

    return render(request, 'add_pair.html', locals())


@login_required(login_url='/login')
def import_all_pairs(request, id):
    exchange = Exchange.objects.get(id=id)

    if request.method == 'GET':
        coins = MasterCoin.objects.all().order_by('symbol')

        try:
            pairs = requests.get(exchange.api_link).json()['data']
        except Exception as e:
            pairs = []

        pairs_ = []
        pairs__ = []
        for ii in pairs:
            base = ii['baseCurrency']
            quote = ii['quoteCurrency']
            if ExchangePair.objects.filter(exchange=exchange, 
                                           base_coin__original_symbol=base, 
                                           quote_coin__original_symbol=quote):
                continue
            bb = MasterCoin.objects.filter(original_symbol=base).count()
            qq = MasterCoin.objects.filter(original_symbol=quote).count()
            if bb and qq:
                if bb > 1 or qq > 1:
                    pairs_.append({ 'base': base, 'quote': quote})
                else:
                    pairs__.append({ 'base': base, 'quote': quote})
                    # segmentation
                    if len(pairs__) > 50:
                        break
    else:
        num_pairs = request.POST.get('num_pairs', 0)

        for idx in range(int(num_pairs)):
            base_coin = request.POST.get('base_coin'+str(idx+1))
            quote_coin = request.POST.get('quote_coin'+str(idx+1))
            
            pair = ExchangePair(exchange=exchange,
                                base_coin_id=base_coin,
                                quote_coin_id=quote_coin,
                                cryptocompare_availability=True,
                                coinapi_availability=True,
                                supported=True,
                                supported_at=datetime.datetime.now())
            pair.save()
        return HttpResponseRedirect(reverse('exchange_detail', kwargs={ 'id': id }))
    return render(request, 'add_all_pair.html', locals())


@login_required(login_url='/login')
def add_coin(request, coin, exchange):
    exchange = Exchange.objects.get(id=exchange)

    coins = MasterCoin.objects.all().order_by('symbol')
    cc_coins = CryptocompareCoin.objects.all()
    cmc_coins = CoinmarketcapCoin.objects.all()
    cp_coins = CoinapiCoin.objects.all()
    cg_coins = CoingeckoCoin.objects.all()
    cml_coins = CoinmarketcalCoin.objects.all()

    coin__ = coin.replace('*', '')
    ccd_coins = [ii.symbol for ii in CryptocompareCoin.objects.filter(symbol__startswith=coin__)]
    ccd_coins = ', '.join(ccd_coins) if len(ccd_coins) > 1 else ''
    cmcd_coins = [ii.symbol for ii in CoinmarketcapCoin.objects.filter(symbol__startswith=coin__)]
    cmcd_coins = ', '.join(cmcd_coins) if len(cmcd_coins) > 1 else ''
    cpd_coins = [ii.symbol for ii in CoinapiCoin.objects.filter(symbol__startswith=coin__)]
    cpd_coins = ', '.join(cpd_coins) if len(cpd_coins) > 1 else ''
    cgd_coins = [ii.symbol for ii in CoingeckoCoin.objects.filter(symbol__startswith=coin__)]
    cgd_coins = ', '.join(cgd_coins) if len(cgd_coins) > 1 else ''
    cmld_coins = [ii.symbol for ii in CoinmarketcalCoin.objects.filter(symbol__startswith=coin__)]
    cmld_coins = ', '.join(cmld_coins) if len(cmld_coins) > 1 else ''

    # for coin's name
    full_name = CoinapiCoin.objects.filter(symbol=coin).first()
    full_name = full_name.name if full_name else ''

    if request.method == 'POST':
        cc = request.POST.get('cc_coin') or None
        cmc = request.POST.get('cmc_coin') or None
        cp = request.POST.get('cp_coin') or None
        cg = request.POST.get('cg_coin') or None
        cml = request.POST.get('cml_coin') or None
        alias = request.POST.get('alias') or None
        new_symbol = request.POST.get('new_symbol') or None
        full_name = request.POST.get('full_name', '')
        is_master = False if alias else True

        cc_name = CryptocompareCoin.objects.get(id=cc).name if cc and cc != '0' else ''
        coin = MasterCoin(cryptocompare=cc,
                          coinmarketcap=cmc,
                          coinapi=cp,
                          coingecko=cg,
                          coinmarketcal=cml,
                          cryptocompare_name=cc_name,
                          symbol=new_symbol,
                          original_symbol=coin,
                          alias_id=alias,
                          supported=True,
                          is_master=is_master,
                          is_trading=True)
        coin.save()
        coin = MasterCoin.objects.get(id=coin.id) # weird

        culture = Culture.objects.filter(name='en_US').first()
        CoinLocale.objects.update_or_create(coin=coin, culture=culture, defaults={ 'name': full_name })

    return render(request, 'add_coin.html', locals())

@login_required(login_url='/login')
def attach_coin(request, coin):
    coin = MasterCoin.objects.get(id=coin)
  
    coins = MasterCoin.objects.all().order_by('symbol')
    cc_coins = CryptocompareCoin.objects.all()
    cmc_coins = CoinmarketcapCoin.objects.all()
    cp_coins = CoinapiCoin.objects.all()
    cg_coins = CoingeckoCoin.objects.all()
    cml_coins = CoinmarketcalCoin.objects.all()

    coin__ = coin.symbol.replace('*', '')
    ccd_coins = [ii.symbol for ii in CryptocompareCoin.objects.filter(symbol__startswith=coin__)]
    ccd_coins = ', '.join(ccd_coins) if len(ccd_coins) > 1 else ''
    cmcd_coins = [ii.symbol for ii in CoinmarketcapCoin.objects.filter(symbol__startswith=coin__)]
    cmcd_coins = ', '.join(cmcd_coins) if len(cmcd_coins) > 1 else ''
    cpd_coins = [ii.symbol for ii in CoinapiCoin.objects.filter(symbol__startswith=coin__)]
    cpd_coins = ', '.join(cpd_coins) if len(cpd_coins) > 1 else ''
    cgd_coins = [ii.symbol for ii in CoingeckoCoin.objects.filter(symbol__startswith=coin__)]
    cgd_coins = ', '.join(cgd_coins) if len(cgd_coins) > 1 else ''
    cmld_coins = [ii.symbol for ii in CoinmarketcalCoin.objects.filter(symbol__startswith=coin__)]
    cmld_coins = ', '.join(cmld_coins) if len(cmld_coins) > 1 else ''

    # for coin's name
    culture = Culture.objects.filter(name='en_US').first()
    cl = CoinLocale.objects.filter(coin=coin, culture=culture).first()
    if cl:
        full_name = cl.name
    else:
        full_name = CoinapiCoin.objects.filter(symbol=coin.original_symbol).first()
        full_name = full_name.name if full_name else ''
    
    if request.method == 'POST':
        coin.cryptocompare = request.POST.get('cc_coin') or None
        coin.coinmarketcap = request.POST.get('cmc_coin') or None
        coin.coinapi = request.POST.get('cp_coin') or None
        coin.coingecko = request.POST.get('cg_coin') or None
        coin.coinmarketcal = request.POST.get('cml_coin') or None        
        coin.alias_id = request.POST.get('alias') or None
        coin.is_master = False if coin.alias_id else True
        coin.symbol = request.POST.get('new_symbol') or None
        full_name = request.POST.get('full_name', '')

        if coin.cryptocompare and coin.cryptocompare != '0':
            coin.cryptocompare_name = CryptocompareCoin.objects.get(id=coin.cryptocompare).name
        coin.save()
        coin = MasterCoin.objects.get(id=coin.id) # weird

        CoinLocale.objects.update_or_create(coin=coin, culture=culture, defaults={ 'name': full_name })

    return render(request, 'add_coin.html', locals())

@login_required(login_url='/login')
def bulk_pair_coin(request):
    page = int(request.GET.get('page', 1))
    prev_page = page - 1 if page > 1 else 1
    page_size = 10
    coins = MasterCoin.objects.all().exclude(cryptocompare__isnull=False, 
                                             coinmarketcap__isnull=False,
                                             coinapi__isnull=False,
                                             coingecko__isnull=False,
                                             coinmarketcal__isnull=False).order_by('symbol')
    total_number = coins.count()
    max_page = int((total_number+page_size-1) / page_size)
    next_page = page + 1 if max_page > page else max_page

    coins = coins[(page-1)*page_size:page*page_size]
    cc_coins = CryptocompareCoin.objects.all()
    cmc_coins = CoinmarketcapCoin.objects.all()
    cp_coins = CoinapiCoin.objects.all()
    cg_coins = CoingeckoCoin.objects.all()
    cml_coins = CoinmarketcalCoin.objects.all()

    if request.method == 'POST':
        for idx in range(page_size):
            coin = request.POST.get('coin'+str(idx+1))
            if coin:
                cc_coin = request.POST.get('cc_coin'+str(idx+1)) or None
                cmc_coin = request.POST.get('cmc_coin'+str(idx+1)) or None
                cp_coin = request.POST.get('cp_coin'+str(idx+1)) or None
                cg_coin = request.POST.get('cg_coin'+str(idx+1)) or None
                cml_coin = request.POST.get('cml_coin'+str(idx+1)) or None

                MasterCoin.objects.filter(id=coin).update(cryptocompare=cc_coin,
                                                          coinmarketcap=cmc_coin,
                                                          coinapi=cp_coin,
                                                          coingecko=cg_coin,
                                                          coinmarketcal=cml_coin)

    return render(request, 'bulk_pair_coin.html', locals())


@csrf_exempt
def supported_coins_(request):
    q = Q(supported=True)
    return _coins(request, q)


def get_support_title(cid):
    return 'YES' if cid > 0 else 'NO' if cid == 0 else 'Not Specified'

def _coins(request, q):
    limit = int(request.POST.get('rowCount'))
    page = int(request.POST.get('current'))
    keyword = request.POST.get('searchPhrase')

    qs = MasterCoin.objects.filter(q & Q(symbol__icontains=keyword)).order_by('symbol')
    total = qs.count()
    coins = []

    cc_coins = [ii.symbol for ii in CryptocompareCoin.objects.all()]
    cmc_coins = [ii.symbol for ii in CoinmarketcapCoin.objects.all()]
    cp_coins = [ii.symbol for ii in CoinapiCoin.objects.all()]

    lstart = (page - 1) * limit
    lend = lstart + limit

    for coin in qs[lstart:lend]:
        status = 'SUPPORTED' if coin.supported else 'On World of Coins' if coin.is_master else 'NEW'
        coin_ = {
            'id': coin.id,
            'symbol': coin.symbol,
            'alias': coin.alias.symbol if coin.alias else '-',
            'cryptocompare': get_support_title(coin.cryptocompare),
            'coinapi': get_support_title(coin.coinapi),
            'cmc': get_support_title(coin.coinmarketcap),
            'gecko': get_support_title(coin.coingecko),
            'cml': get_support_title(coin.coinmarketcal),
            'supported': get_support_title(coin.supported),
            'status': status
        }
        coins.append(coin_)

    return JsonResponse({
        "current": page,
        "rowCount": limit,
        "rows": coins,
        "total": total
        }, safe=False)

@csrf_exempt
def exchanges_(request):
    limit = int(request.POST.get('rowCount'))
    page = int(request.POST.get('current'))
    keyword = request.POST.get('searchPhrase')

    qs = Exchange.objects.filter(name__icontains=keyword)
    total = qs.count()
    exchanges = []

    lstart = (page - 1) * limit
    lend = lstart + limit

    for exchange in qs[lstart:lend]:
        exchange_ = {
            'id': exchange.id,
            'name': exchange.name,
            'cryptocompare': 'YES' if exchange.cryptocompare > 0 else 'NO',
            'coinapi': 'YES' if exchange.coinapi > 0 else 'NO',
            'supported': 'YES' if exchange.supported else 'NO'
        }
        exchanges.append(exchange_)

    return JsonResponse({
        "current": page,
        "rowCount": limit,
        "rows": exchanges,
        "total": total
        }, safe=False)


@csrf_exempt
def supported_exchanges_(request):
    limit = int(request.POST.get('rowCount'))
    page = int(request.POST.get('current'))
    keyword = request.POST.get('searchPhrase')

    qs = Exchange.objects.filter(name__icontains=keyword, supported=True).order_by('name')
    total = qs.count()
    exchanges = []

    lstart = (page - 1) * limit
    lend = lstart + limit

    master_coins = [ii.original_symbol for ii in MasterCoin.objects.all()]

    for exchange in qs[lstart:lend]:
        pairs = exchange.pairs.all()
        coins = [pair.base_coin.symbol for pair in pairs]
        num_pairs = pairs.count()

        # try:
        #     num_pairs = len(requests.get(exchange.api_link).json()['data'])
        # except Exception as e:
        #     num_pairs = 0

        num_new_pairs = 0
        num_new_coins = 0

        coins = []
        for ii in TempPair.objects.filter(exchange=exchange.name):
            num_new_pairs += 1
            coins += ii.pair.strip().split('-')

        for ii in set(coins):
            if ii not in master_coins:
                num_new_coins += 1

        exchange_ = {
            'id': exchange.id,
            'exchange': exchange.name,
            'num_coins': len(set(coins)),
            'num_pairs': num_pairs,
            'num_new_pairs': num_new_pairs,
            'num_new_coins': num_new_coins
        }
        exchanges.append(exchange_)

    return JsonResponse({
        "current": page,
        "rowCount": limit,
        "rows": exchanges,
        "total": total
        }, safe=False)


@csrf_exempt
def exchange_detail_(request, id):
    limit = int(request.POST.get('rowCount'))
    page = int(request.POST.get('current'))
    keyword = request.POST.get('searchPhrase')
    lstart = (page - 1) * limit
    lend = lstart + limit

    exchange = Exchange.objects.get(id=id)
    qs = exchange.pairs.filter(Q(base_coin__symbol__icontains=keyword) 
                             | Q(quote_coin__symbol__icontains=keyword))
    s_pairs = {}
    for ii in qs:
        pair = ii.base_coin.symbol + ' / ' + ii.quote_coin.symbol
        s_pairs[pair] = str(ii.supported_at) if ii.supported_at else ''

    master_coins = [ii.symbol for ii in MasterCoin.objects.all()]
    cc_pairs = ['{}-{}-{}'.format(ii.exchange.upper(), ii.base_coin, ii.quote_coin) for ii in CryptocomparePair.objects.all() if keyword.upper() in ii.base_coin or keyword.upper() in ii.quote_coin]
    cp_pairs = ['{}-{}-{}'.format(ii.exchange.upper(), ii.base_coin, ii.quote_coin) for ii in CoinapiPair.objects.all() if keyword.upper() in ii.base_coin or keyword.upper() in ii.quote_coin]

    result_a = {}
    result_b = {}
    result_c = {}

    try:
        pairs = requests.get(exchange.api_link).json()['data']
        for ii in pairs:
            base = ii['baseCurrency']
            quote = ii['quoteCurrency']
            pair = base + ' / ' + quote
            if keyword.lower() not in pair.lower():
                continue

            coin_supported = base in master_coins
            quote_coin_supported = quote in master_coins
            supported = 'YES' if pair in s_pairs else 'NO'

            ii_ = {
                'pair': pair,
                'exchange': id,
                'coin': base,
                'coin_supported': coin_supported,
                'quote_coin': quote,
                'quote_coin_supported': quote_coin_supported,
                'supported': supported,
                'supported_at': s_pairs.get(pair, ''),
            }

            if not coin_supported or not quote_coin_supported:
                result_a[pair] = ii_
            elif supported == 'NO':
                result_b[pair] = ii_
            else:
                result_c[pair] = ii_
    except Exception as e:
        pass

    result = []
    for k, v in sorted(result_a.items()):       # unsupported coins
        result.append(v)
    for k, v in sorted(result_b.items()):       # unsupported pairs
        result.append(v)
    for k, v in sorted(result_c.items()):       # supported pairs
        result.append(v)

    pre_coin = None
    for ii in result[lstart:lend]:
        [base, quote] = ii['pair'].split(' / ')
        coin = '' if pre_coin == base else base
        ii['coin'] = coin
        pre_coin = base

        cc_support = '{}-{}-{}'.format(exchange.cryptocompare.upper(), base, quote) in cc_pairs
        cp_support = '{}-{}-{}'.format(exchange.coinapi.upper(), base, quote) in cp_pairs

        intersect = ''
        if cc_support and cp_support:
            intersect = 'Coinapi / Cryptocompare'
        elif cc_support:
            intersect = 'Cryptocompare'
        elif cp_support:
            intersect = 'Coinapi'
        ii['is_master'] = intersect

    return JsonResponse({
        "current": page,
        "rowCount": limit,
        "rows": result[lstart:lend],
        "total": len(result)
    }, safe=False)

def download_icon(request, id):
    coin = MasterCoin.objects.get(id=id)
    if coin.cryptocompare:
        url = CryptocompareCoin.objects.get(id=coin.cryptocompare).image_uri

        url_ = "https://www.cryptocompare.com" + url
        headers = { 'cookie': '__cfduid=d4f723e7ca0160143b1c13ac7bf1819741528343396; _tuts_session=d04a378a2fdc02aa0b2fdf22d285452a; _ga=GA1.2.2058121609.1528343396; _gid=GA1.2.541871630.1528343396; __gads=ID=e0ebfc441b1d895d:T=1528343400:S=ALNI_MZpYcNa89niIKwttMQ54vlOpzhdyQ' }

        for size in [16, 32, 48, 64, 128]:
            url = url_ + '?width={}'.format(size)
            file_name = coin.symbol.replace('*', 'star')
            file_path = settings.BASE_DIR + '/static/icons/{}-{}.png'.format(file_name, size)
            print url, file_path
            info = requests.get(url, headers=headers)
            with open(file_path, "wb") as file:
                file.write(info.content)
            coin.image_uri = '/static/icons/{}'.format(file_name)
            coin.save()
        return HttpResponse('success')
    return HttpResponse('Icon is not available.')

def get_csv(request):
    ex = request.GET.get('ex', 'binance')  # binance or bitfinex
    timeframe = request.GET.get('timeframe', '1min')    # 1min or 1day
    start = request.GET.get('start')
    end = request.GET.get('end')
    timezone = request.GET.get('ex', 0)    # -13 to 13

    path = "/tmp/.qobit.csv"

    query = """
        SELECT time_bucket('1440 minutes', open_time) AS time, base_currency_id, quote_currency_id, first(open, open_time) AS open, MAX(high) AS high, MIN(low) AS low, last(close, open_time) AS close, SUM(volume) AS volume 
        FROM binance_rates 
        WHERE open_time >= '2018-03-15' and open_time <= '2018-03-20' 
        GROUP BY base_currency_id, quote_currency_id, time
    """

    with connection.cursor() as cursor:
        cursor.execute(query, [])

        csv_fields = [col[0] for col in cursor.description]
        result = []
        
        with open(path, 'w') as f:
            f.write(','.join(csv_fields)+'\n')

            for row in cursor.fetchall():
                f.write(','.join([str(ii) for ii in row])+'\n')
    
    wrapper = FileWrapper( open( path, "r" ) )
    content_type = mimetypes.guess_type( path )[0]

    response = HttpResponse(wrapper, content_type = content_type)
    response['Content-Length'] = os.path.getsize( path ) # not FileField instance
    response['Content-Disposition'] = 'attachment; filename=%s' % smart_str( os.path.basename( path ) )
    return response

def get_pairs_info(request):
    # get lastest pair information
    ex = request.GET.get('ex')  # binance or bitfinex
    query = """
        select * from binance_rates order by open_time desc limit 361;
    """
    # check duplicate with list
    with connection.cursor() as cursor:
        cursor.execute(query, [])

        csv_fields = [col[0] for col in cursor.description]
        result = ','.join(csv_fields)+'<br>'
        
        for row in cursor.fetchall():
            result += ','.join([str(ii) for ii in row])+'<br>'

    return HttpResponse(result)
