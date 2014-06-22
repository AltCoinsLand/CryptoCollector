import json
from collections import OrderedDict

from django.template.response import TemplateResponse
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from models import wallet_classes
from forms import WalletForm

@login_required
def wallets(request):
    """
    Show all wallets for logged in user.
    """
    form = WalletForm()
    if request.POST:
        form = WalletForm(request.POST)
        if form.is_valid():
            try:
                form.make_wallet(request.user)
            except NotImplementedError:
                curr = form.cleaned_data['type'].upper()
                messages.error(request, "Can't create wallets of type %s yet" % curr)
            return HttpResponseRedirect("/wallets/")

    wallets = OrderedDict()
    no_wallets = True
    for symbol, Wallet in wallet_classes.items():
        wals = list(Wallet.objects.filter(owner__id=request.user.id))
        wallets[symbol] = wals
        if len(wals) >= 1:
            no_wallets = False

    return TemplateResponse(request, 'wallet.html', {
        'wallets_for_all_currencies': wallets,
        'no_wallets': no_wallets,
        'new_wallet_form': form,
    })

@login_required
def get_transactions(request):
    """
    API call for getting transactions for a wallet.
    Called by front end browser ajax, returns JSON.
    """
    symbol, pk = request.GET['js_id'].split('-')
    fiat_symbol = request.GET.get('fiat', 'usd')
    wallet = wallet_classes[symbol].objects.filter(pk=pk).filter(
        owner__id=request.user.id
    ).get()
    transactions = wallet.get_transactions()
    j = json.dumps([
        {
            'txid': tx.txid,
            'historical_price': tx.historical_price(fiat_symbol),
            'amount': tx.amount,
            'date': tx.date.isoformat(),
        } for tx in transactions
    ])
    return HttpResponse(j, content_type="application/json")

@login_required
def get_value(request):
    """
    API call for getting the most recent price for a wallet.
    Al requests via this way bypass cache.
    """
    symbol, pk = request.GET['js_id'].split('-')
    wallet = wallet_classes[symbol].objects.filter(pk=pk).filter(
        owner__id=request.user.id
    ).get()
    res = {
        'fiat_exchange': wallet.get_fiat_exchange(hard_refresh=True),
        'wallet_value': wallet.get_value(hard_refresh=True),
        'fiat_value': wallet.get_fiat_value(),
    }
    return HttpResponse(json.dumps(res), content_type="application/json")

@login_required
def get_private_key(request):
    symbol, pk = request.GET['js_id'].split('-')
    wallet = wallet_classes[symbol].objects.filter(pk=pk).filter(
        owner__id=request.user.id
    ).get()
    return HttpResponse(wallet.private_key, content_type="text/plain")

@login_required
def save_private_key(request):
    symbol, pk = request.POST['js_id'].split('-')
    wallet = wallet_classes[symbol].objects.filter(pk=pk).filter(
        owner__id=request.user.id
    ).get()
    wallet.private_key = request.POST['private_key']
    wallet.save();
    messages.info(request, "Private key succesfully added to <strong>%s</strong>" % wallet.name)
    return HttpResponseRedirect("/wallets/")

@login_required
def paper_wallet(request):
    """
    Either pass in a single jsid is a wallet, or pass in nothing to generate
    a page with all the paper wallets from your account. It skips wallets
    that do not have a private key, and that have no value stored in them.
    """
    js_id = request.GET.get('js_id', None)
    if js_id:
        symbol, pk = js_id.split("-")
        wallet = wallet_classes[symbol].objects.filter(pk=pk).filter(
            owner__id=request.user.id
        ).get()
        wallets = [wallet]
    else:
        wallets = []
        for symbol, Wallet in wallet_classes.items():
            wals = list(
                Wallet.objects.filter(owner__id=request.user.id)
                .exclude(private_key='')
            )
            wallets.extend(wals)

    return TemplateResponse(request, 'paper_wallet.html', {
        'wallets': wallets,
    })
