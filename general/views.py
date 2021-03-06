import os
import json
import requests
import datetime
import mimetypes
from pytz import timezone

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
from general.forms import *
from general.utils import *

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
def events(request):
    return render(request, 'events.html', {})


@login_required(login_url='/login')
def exchanges(request):
    return render(request, 'exchanges.html', {})


@login_required(login_url='/login')
def qbtagg_quotes(request):
    ids = [ii.coin.id for ii in QBTAGGQuote.objects.filter(is_deleted=False)]
    coins = MasterCoin.objects.filter(type_is_crypto=False).exclude(id__in=ids).order_by('symbol')    
    return render(request, 'qbtagg_quotes.html', locals())


@login_required(login_url='/login')
def supported_exchanges(request):
    return render(request, 'supported_exchanges.html', {})


@login_required(login_url='/login')
def exchange_detail(request, id):
    exchange = Exchange.objects.get(id=id)
    return render(request, 'exchange_detail.html', { "exchange": exchange })


@login_required(login_url='/login')
def event_detail(request, id):
    event = CoinEvent.objects.get(id=id) if id else None
    if request.method == 'GET':
        form = EventForm(instance=event)
    else:
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            event = form.save()
            if not event.created_date:  # for brand new
                event.created_date = datetime.datetime.now()
                event.save()
            return HttpResponseRedirect(reverse('event_detail', kwargs={ 'id': event.id }))

    locales = Culture.objects.all()
    status = EVENT_STATUS
    coins = MasterCoin.objects.all()
    categories = CoinEventCategory.objects.all()
    return render(request, 'event_detail.html', locals())


@csrf_exempt
def desc_translate(request):
    desc = request.POST.get('desc').encode('ascii', 'ignore')
    return HttpResponse(translate(desc))


@login_required(login_url='/login')
def locale_event_add(request, eid, lid):
    event = CoinEvent.objects.get(id=eid)
    levent = event.coineventlocale_set.filter(culture_id=int(lid)).first()

    if request.method == 'GET':
        event_ = model_to_dict(event)
        event_['title'] = levent.title
        event_['description'] = levent.description
        event_['status'] = levent.status
        event_['culture'] = levent.culture
        form = EventForm(initial=event_)
    else:
        form = EventForm(request.POST)
        if form.is_valid():
            event.coins = form.cleaned_data['coins']
            event.cml_coins = form.cleaned_data['cml_coins']
            event.proof = form.cleaned_data['proof']
            event.source = form.cleaned_data['source']
            event.is_hot = form.cleaned_data['is_hot']
            event.categories = form.cleaned_data['categories']
            event.can_occur_before = form.cleaned_data['can_occur_before']
            event.date_event_start = form.cleaned_data['date_event_start']
            event.save()

            levent.title = form.cleaned_data['title']
            levent.description = form.cleaned_data['description']
            levent.status = form.cleaned_data['status']
            levent.save()
            return HttpResponseRedirect(reverse('locale_event_add', kwargs={ 'eid': eid, 'lid': lid }))

    locales = Culture.objects.all()
    status = EVENT_STATUS
    coins = MasterCoin.objects.all()
    categories = CoinEventCategory.objects.all()    
    return render(request, 'event_detail.html', locals())


@login_required(login_url='/login')
def locale_coin(request, cid, lid):
    coin = MasterCoin.objects.get(id=cid)
    lcoin = coin.coinlocale_set.filter(culture_id=int(lid)).first()

    if request.method == 'GET':
        form = CoinLocaleForm(instance=lcoin, initial={ 'culture': int(lid), 'edited': True })
    else:
        form = CoinLocaleForm(request.POST, instance=lcoin)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('locale_coin', kwargs={ 'cid': cid, 'lid': lid }))

    locales = Culture.objects.all()
    return render(request, 'coin_locale.html', locals())


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
        return render(request, 'add_all_pair.html', locals())
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

        defaults = {
            'cryptocompare': cc,
            'coinmarketcap': cmc,
            'coinapi': cp,
            'coingecko': cg,
            'coinmarketcal': cml,
            'cryptocompare_name': cc_name,        
            'supported': True,
            'is_master': is_master,
            'is_trading': True
        }

        coin, is_new = MasterCoin.objects.update_or_create(symbol=new_symbol,
                                                      original_symbol=coin,
                                                      alias_id=alias,
                                                      defaults=defaults)
        coin = MasterCoin.objects.get(id=coin.id) # weird
        culture = Culture.objects.filter(name='en_US').first()
        CoinLocale.objects.update_or_create(coin=coin, culture=culture, defaults={ 'name': full_name })

    return render(request, 'add_coin.html', locals())


@login_required(login_url='/login')
def attach_coin(request, coin):
    edit_button = True
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


def build_query(ds, opt):
    if opt == '1':
        return { ds+'__isnull': True }
    elif opt == '2':
        return { ds+'__gt': 0 }
    elif opt == '3':
        return { ds: 0 }


@login_required(login_url='/login')
def bulk_pair_coin(request):
    mode = request.GET.get('mode', 'default')
    page = int(request.GET.get('page', 1))
    prev_page = page - 1 if page > 1 else 1
    page_size = 10

    if mode == 'default':
        coins = MasterCoin.objects.filter(alias__isnull=True) \
                                  .exclude(cryptocompare__isnull=False, 
                                           coinmarketcap__isnull=False,
                                           coinapi__isnull=False,
                                           coingecko__isnull=False,
                                           coinmarketcal__isnull=False) \
                                  .order_by('symbol')
    else:
        if request.GET.get('initial'):
            q = Q(symbol=-1)
        else:
            q__ = request.GET.get('q', '')
            q = Q(symbol__icontains=q__) & Q(alias__isnull=True)
            fts = ['cryptocompare', 'coinapi', 'coinmarketcap', 'coingecko', 'coinmarketcal']
            for fi in fts:
                q_ = build_query(fi, request.GET.get(fi))
                if q_:
                    q &= Q(**q_)
        coins = MasterCoin.objects.filter(q)

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
def events_(request):
    limit = int(request.POST.get('rowCount'))
    page = int(request.POST.get('current'))
    keyword = request.POST.get('searchPhrase')
    lstart = (page - 1) * limit
    lend = lstart + limit

    result = []
    qs = CoinEvent.objects.filter(Q(title__icontains=keyword) | Q(description__icontains=keyword))
    total = qs.count()

    for ii in qs[lstart:lend]:
        result.append({
            'id': ii.id,
            'title': ii.title,
            'date_event': str(ii.date_event_start.date()),
            'created_date': str(ii.created_date).split('+')[0].split('.')[0],
            'status_en': ii.status,
            'status_zh': ii.coineventlocale_set.all().first().status,
            'mapped': 'YES' if ii.coins.all() else 'NO'
        })

    return JsonResponse({
        "current": page,
        "rowCount": limit,
        "rows": result,
        "total": total
    }, safe=False)


@csrf_exempt
def qbtagg_quotes_(request):
    limit = int(request.POST.get('rowCount'))
    page = int(request.POST.get('current'))

    qs = QBTAGGQuote.objects.filter(is_deleted=False)

    total = qs.count()
    coins = []

    for ii in qs:
        coin_ = {
            'id': ii.coin.id,
            'symbol': ii.coin.symbol,
            'cryptocompare': get_support_title(ii.coin.cryptocompare),
            'coinapi': get_support_title(ii.coin.coinapi),
            'cmc': get_support_title(ii.coin.coinmarketcap),
            'gecko': get_support_title(ii.coin.coingecko),
            'cml': get_support_title(ii.coin.coinmarketcal)
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
        pair = ii.base_coin.original_symbol + ' / ' + ii.quote_coin.original_symbol
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
            base = ii['baseCurrency'].strip()
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


def get_resolution(timeframe):
    try:
        mul = { 'M': 1, 'H': 60, 'D': 1440 }
        resolution = int(timeframe[:-1]) * mul[timeframe[-1]]
    except Exception as e:
        resolution = 0
    return resolution

def get_csv(request):
    try:
        ex = request.GET.get('ex', 'binance')  # binance or bitfinex
        if ex not in ['binance', 'bitfinex']:
            return HttpResponse('The exchange is not supported. Type binance or bitfinex')

        vol = 'volume' if ex == 'binance' else 'base_volume'
        pair = request.GET.get('pair')
        timeframe = request.GET.get('timeframe', '1M')    # 1min or 1day
        resolution = get_resolution(timeframe)
        if not resolution:
            return HttpResponse('The timeframe is not supported. Type 1M/5M/15M/30M/1H/4H/1D')

        start = request.GET.get('start')
        end = request.GET.get('end')
        tz = request.GET.get('tz', 0)    # -13 to 13

        base_coin = MasterCoin.objects.filter(symbol=pair.split('-')[0].upper()).first()
        quote_coin = MasterCoin.objects.filter(symbol=pair.split('-')[-1].upper()).first()

        if not base_coin or not quote_coin:
            return HttpResponse('The pair is not supported in the exchange.')

        path = "/tmp/.{}-{}-{}.csv".format(ex, pair, start)

        query = """
            SELECT time_bucket('{} minutes', open_time) AS trade_time, 
                   first(open, open_time) AS open, MAX(high) AS high, MIN(low) AS low, 
                   last(close, open_time) AS close, SUM({}) AS volume 
            FROM {}_rates 
            WHERE open_time >= '{}' and open_time <= '{}' and 
                  base_currency_id = {} and quote_currency_id = {} 
            GROUP BY trade_time
        """

        query = query.format(resolution, vol, 'old_binance' if ex == 'binance' else ex, 
                             start+':00+00:00',
                             end+':00+00:00',
                             base_coin.id,
                             quote_coin.id)

        print query
        with connection.cursor() as cursor:
            cursor.execute(query, [])

            result = []
            
            with open(path, 'w') as f:
                f.write('date, time, open, high, low, close, volume, currency\n')

                for row in cursor.fetchall():
                    row_ = list(row)
                    row_.insert(1, row_[0].strftime('%H:%M'))
                    row_[0] = row_[0].strftime('%Y.%m.%d')
                    row_.append(pair.replace('-', '').upper())
                    f.write(','.join([str(ii) for ii in row_])+'\n')
        
        wrapper = FileWrapper( open( path, "r" ) )
        content_type = mimetypes.guess_type( path )[0]

        response = HttpResponse(wrapper, content_type = content_type)
        response['Content-Length'] = os.path.getsize( path ) # not FileField instance
        response['Content-Disposition'] = 'attachment; filename=%s' % smart_str( os.path.basename( path ) )
        return response
    except Exception as e:
        print e
        return HttpResponse('Please provide valid parameters')


def get_pairs_info(request):
    ex = request.GET.get('ex', '')  # binance or bitfinex
    exchange = Exchange.objects.filter(name=ex.upper()).first()
    result = 'pair, start date\n'
    if exchange:
        for pair in  exchange.pairs.all().order_by('base_coin__symbol', 'quote_coin__symbol'):
            result += '{}-{},{}\n'.format(pair.base_coin.symbol, pair.quote_coin.symbol, str(pair.data_start))
    else:
        result = 'Please provide a valid exchange.'
    return HttpResponse(result)


@login_required(login_url='/login')
def add_qbtagg_quote(request):
    quote_coin = request.POST.get('qbtagg_quote')
    QBTAGGQuote.objects.create(coin_id=quote_coin)
    return HttpResponseRedirect(reverse('qbtagg_quotes'))
