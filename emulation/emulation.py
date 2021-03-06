import fcntl
import json
import logging
import math
import uuid
from datetime import datetime

import numpy as np
import redis as _redis
import requests

import settings

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT)

redis = _redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)


class Logger:
    def __init__(self, name, filename):
        self.logger = logging.getLogger(name)
        fh = logging.FileHandler(filename)
        formatter = logging.Formatter(FORMAT)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.setLevel(logging.DEBUG)

    def pretty_print(self, *args, **kwargs):
        string = ' '.join(map(str, args))
        return self.logger.debug(string)


logger = Logger(__name__, 'emulation.log')


def create_users(url, players):
    '''Создаем юзеров на серваке'''
    for i in players:
        requests.post(url + 'api/v1/user/create-user/',
                      headers={'Content-type': 'application/json'},
                      json={
                          'email': i.email,
                          'password': i.password
                      })


def get_tokens_or_create_user(url, players):
    '''Получаем токены c сервера
        Если токентов нет, то регистрируем пользовотеля
    '''
    for i in players:
        rq = requests.post(url + 'api/v1/user/api-token-auth/',
                           json={
                               'email': i.email,
                               'password': i.password
                           })
        if rq.status_code == 400:
            requests.post(url + 'api/v1/user/create-user/',
                          headers={'Content-type': 'application/json'},
                          json={
                              'email': i.email,
                              'password': i.password
                          })
            i.token = requests.post(url + 'api/v1/user/api-token-auth/',
                                    json={
                                        'email': i.email,
                                        'password': i.password
                                    }).json()['token']
        else:
            i.token = rq.json()['token']


def dump_tokens(filename, players):
    '''Загрузка токентов в файл'''
    dic = {}

    for n, pl in enumerate(players):
        dic[n] = pl.token
    with open(filename, 'w') as outfile:
        json.dump(dic, outfile)


def load_tokens(filename, players, num):
    '''Загружаем токены из файла'''
    with open(filename, 'r') as file:
        tokens = json.load(file)
    for i in range(num):
        players[i].token = tokens[str(i)]


def write_stats(url, instrument_id, emulation_uuid):
    logger.pretty_print(
        'Writing stats for emulation_uuid: {}, instrument_id: {}'.format(
            emulation_uuid, instrument_id))
    res = requests.post(url + 'api/v1/user/stats/',
                        json={
                            'instrument_id': instrument_id,
                            'emulation_uuid': str(emulation_uuid),
                        })
    if res.status_code > 300:
        logger.pretty_print('Error writing stats', res.text)


def delete_orders(url, bank):
    return requests.delete(url + 'api/v1/user/orders/delete-all/',
                           headers={'Authorization': 'JWT ' + bank.token})


def create_new_instrument(url, bank):
    return requests.post(url + 'api/v1/user/instruments/',
                         headers={
                             'Authorization': 'JWT ' + bank.token
                         },
                         json={
                             'name': 'emulation #' + str(datetime.now())
                         }).json()['id']


class Person:
    def __init__(self,
                 email,
                 targetreturn=0.12,
                 money=100,
                 sellp=.2,
                 buyp=.2,
                 skipp=.2,
                 assets=0,
                 maxproportion=0.5,
                 minproportion=0.1):
        self.email = email
        self.password = 'abc123PPHUILA'
        self.token = ''
        self.curmoney = money
        self.curassets = assets
        self.targetreturn = targetreturn
        self.curreturn = 0
        self.assets, self.money = [], []
        self.assets.append(self.curassets)
        self.money.append(self.curmoney)
        self.maxproportion, self.minproportion = maxproportion, minproportion
        self.buyp, self.skipp, self.sellp = buyp, skipp, sellp

    def action(self, url, assetreturn, inst_id):
        buy, sell = self.buyp, self.sellp
        deltareturn = self.targetreturn - self.curreturn
        if deltareturn >= 0:
            buy = buy + (deltareturn) / self.targetreturn * (
                1 - self.skipp - self.buyp - self.sellp)
        else:
            sell = sell - deltareturn / self.curreturn * (
                1 - self.skipp - self.buyp - self.sellp)
        rnd = np.random.uniform()
        if rnd <= buy:
            return self.place_buy(url, deltareturn, assetreturn, inst_id)
        elif rnd <= buy + sell:
            return self.place_sell(url, deltareturn, assetreturn, inst_id)
        else:
            return self.skip()

    def skip(self):
        return {'type': 'skip', 'remaining_sum': 0, 'price': 0, 'status': 0}

    def sell(self, deltareturn, assetreturn):
        proportion = self.minproportion - np.minimum(deltareturn / \
                                                     np.maximum(
                                                         self.targetreturn,
                                                         self.curreturn) * (
                                                             self.maxproportion - self.minproportion),
                                                     0)
        rtrn = assetreturn * (
            1 - np.sign(deltareturn) * 0.01 * np.random.exponential(
                np.abs(deltareturn /
                       np.maximum(self.targetreturn, self.curreturn))))
        price = 1 / (1 + rtrn)
        return proportion * self.curassets, rtrn, price

    def buy(self, deltareturn, assetreturn):
        proportion = self.minproportion + \
                     np.maximum(deltareturn / np.maximum(self.targetreturn,
                                                         self.curreturn) * \
                                (self.maxproportion - self.minproportion), 0)
        rtrn = assetreturn * (
            1 + np.sign(deltareturn) * 0.01 * np.random.exponential(
                np.abs(deltareturn /
                       np.maximum(self.targetreturn, self.curreturn))))
        price = 1 / (1 + rtrn)
        return (proportion * self.curmoney, rtrn, price)

    def update_curretrun(self):
        self.curreturn = (self.curmoney + self.curassets) / self.money[0]

    def put_balance(self, url, inst_id):
        id = requests.get(url +
                          'api/v1/user/instrument-balance/?instrument_id=' +
                          str(inst_id),
                          headers={
                              'Authorization': 'JWT ' + self.token
                          }).json()[0]['id']
        requests.put(url + 'api/v1/user/instrument-balance/' + str(id),
                     json={
                         'amount': self.curassets
                     },
                     headers={
                         'Authorization': 'JWT ' + self.token
                     }).json()
        id = requests.get(url + 'api/v1/user/fiat-balance/',
                          headers={
                              'Authorization': 'JWT ' + self.token
                          }).json()['id']
        requests.put(url + 'api/v1/user/fiat-balance/' + str(id),
                     json={
                         'amount': self.curmoney
                     },
                     headers={
                         'Authorization': 'JWT ' + self.token
                     }).json()

    def update_balance(self, url, inst_id):
        self.curassets = requests.get(
            url + 'api/v1/user/instrument-balance/?instrument_id=' +
            str(inst_id),
            headers={
                'Authorization': 'JWT ' + self.token
            }).json()[0]['amount']
        self.assets.append(self.curassets)
        self.curmoney = requests.get(url + 'api/v1/user/fiat-balance/',
                                     headers={
                                         'Authorization': 'JWT ' + self.token
                                     }).json()['amount']
        self.money.append(self.curmoney)

        self.curreturn = (self.curmoney + self.curassets - self.money[0]) / \
                         self.money[0]
        price = requests.get(url + 'api/v1/user/price/?instrument_id=' +
                             str(inst_id)).json()['result']
        if price:
            self.targetreturn = (1 - price) / price

    def place_buy(self, url, deltareturn, assetreturn, inst_id):
        amount, assetreturn, price = self.buy(deltareturn, assetreturn)
        return requests.post(url + 'api/v1/user/orders/',
                             headers={
                                 'Authorization': 'JWT ' + self.token
                             },
                             json={
                                 'type': 'buy',
                                 'price': math.floor(price * 1e4) / 1e4,
                                 'total_sum': math.floor(amount * 1e4) / 1e4,
                                 'expires_in': 4,
                                 'instrument_id': inst_id
                             }).json()

    def place_sell(self, url, deltareturn, assetreturn, inst_id):
        amount, assetreturn, price = self.sell(deltareturn, assetreturn)
        return requests.post(url + 'api/v1/user/orders/',
                             headers={
                                 'Authorization': 'JWT ' + self.token
                             },
                             json={
                                 'type': 'sell',
                                 'price': math.floor(price * 1e4) / 1e4,
                                 'total_sum': math.floor(amount * 1e4) / 1e4,
                                 'expires_in': 4,
                                 'instrument_id': inst_id
                             }).json()

    def info(self):
        logger.pretty_print('Bot name', self.email, 'Cur money: ',
                            self.curmoney, ' Cur assets: ', self.curassets,
                            'Target return: ', self.targetreturn,
                            ' Cur return: ', self.curreturn)


class Bank:
    def __init__(self, email="bank1@mail.ru", assets=1000, money=0):
        self.curassets = assets
        self.curmoney = money
        self.assets, self.money = [], []
        self.assets.append(self.curassets)
        self.money.append(self.curmoney)
        self.token = 0
        self.email = email
        self.password = "abc123PPHUILA"

    def put_balance(self, url, inst_id):
        idbank = requests.get(
            url + 'api/v1/user/instrument-balance/?instrument_id=' +
            str(inst_id),
            headers={
                'Authorization': 'JWT ' + self.token
            }).json()[0]['id']
        requests.put(url + 'api/v1/user/instrument-balance/' + str(idbank),
                     json={
                         'amount': self.curassets
                     },
                     headers={
                         'Authorization': 'JWT ' + self.token
                     }).json()
        idbank = requests.get(url + 'api/v1/user/fiat-balance/',
                              headers={
                                  'Authorization': 'JWT ' + self.token
                              }).json()['id']
        requests.put(url + 'api/v1/user/fiat-balance/' + str(idbank),
                     json={
                         'amount': self.curmoney
                     },
                     headers={
                         'Authorization': 'JWT ' + self.token
                     }).json()

    def place_order(self, url, curreturn, inst_id):
        curprice = 1 / (1 + curreturn)
        return requests.post(url + 'api/v1/user/orders/',
                             headers={
                                 'Authorization': 'JWT ' + self.token
                             },
                             json={
                                 'type': 'sell',
                                 'price': math.floor(curprice * 1e4) / 1e4,
                                 'total_sum':
                                 math.floor(self.curassets * 1e4) / 1e4,
                                 'expires_in': 4,
                                 'instrument_id': inst_id
                             }).json()

    def update_balance(self, url, inst_id):
        self.curassets = requests.get(
            url + 'api/v1/user/instrument-balance/?instrument_id=' +
            str(inst_id),
            headers={
                'Authorization': 'JWT ' + self.token
            }).json()[0]['amount']
        self.assets.append(self.curassets)
        self.curmoney = requests.get(url + 'api/v1/user/fiat-balance/',
                                     headers={
                                         'Authorization': 'JWT ' + self.token
                                     }).json()['amount']
        self.money.append(self.curmoney)

    def create(self, url):
        requests.post(url + 'api/v1/user/create-user/',
                      headers={'Content-type': 'application/json'},
                      json={
                          'email': self.email,
                          'password': self.password
                      })

    def get_token(self, url):
        self.token = requests.post(url + 'api/v1/user/api-token-auth/',
                                   json={
                                       'email': self.email,
                                       'password': self.password
                                   }).json()['token']


def dump_info(filename, players, bank):
    dic = {}
    dic['bank_'] = [bank.assets, bank.money]
    for i in players:
        dic[i.email] = [i.assets, i.money]
    with open(filename, 'w') as outfile:
        json.dump(dic, outfile)


def emulate(
        emulation_uuid,
        url=None,
        duration=None,
        yearreturn=None,
        bank=None,
        peoples=None,
        inst_id=1,
):
    """

    :param emulation_uuid:
    :param url:
    :param duration:
    :param yearreturn:
    :param bank:
    :param peoples:
    :param inst_id:
    """
    keys = ['type', 'remaining_sum', 'price', 'status']
    for i in range(duration):
        delete_orders(url, bank)
        logger.pretty_print('\n\nDay ', i)
        curreturn = (duration / 365) * (yearreturn - yearreturn / duration * i)
        perm = np.random.permutation(len(peoples))
        money, assets = 0, 0

        if bank.curassets >= 0:
            logger.pretty_print('Bank order')
            order = bank.place_order(url, 1.1 * curreturn, inst_id)
            for k in keys:
                logger.pretty_print(order[k])

        for ind in perm:
            order = peoples[ind].action(url, curreturn, inst_id)
            logger.pretty_print('\nOrder #', ind)
            for k in keys:
                logger.pretty_print(order[k])

        # logger.pretty_print()

        for player in peoples:
            player.update_balance(url, inst_id)
            player.info()
            money += player.curmoney
            assets += player.curassets

        bank.update_balance(url, inst_id)
        money += bank.curmoney
        assets += bank.curassets
        logger.pretty_print('Bank money:', bank.curmoney, ' Bank assets: ',
                            bank.curassets)
        logger.pretty_print('Money:', money, ' Assets: ', assets)
        print(bank.curassets)
        write_stats(url, inst_id, emulation_uuid)


def try_instrument(url, bank, inst_id):
    ins = inst_id
    if len(
            requests.get(url +
                         'api/v1/user/instrument-balance/?instrument_id=' +
                         str(inst_id),
                         headers={
                             'Authorization': 'JWT ' + bank.token
                         }).json()) == 0:
        ins = create_new_instrument(url, bank)
    return ins


def run_emulation(emulation_uuid,
                  url='http://client-api.dlbas.me/',
                  days=50,
                  yearreturn=.15,
                  nplaysers=3,
                  meanmoney=100,
                  assets=800,
                  meantargetreturn=.15,
                  inst_id=17):
    """
    Runs emulation. Throws BlockingIOError exception if another round of emulation was already ran.
    :param emulation_uuid:
    :param url:
    :param days:
    :param yearreturn:
    :param nplaysers:
    :param meanmoney:
    :param assets:
    :param meantargetreturn:
    :param inst_id:
    """
    with open(settings.LOCK_FILE_NAME, 'w') as lockfile:
        with redis.lock(str(emulation_uuid) + '__lock'):
            fcntl.flock(
                lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB
            )  # locks until emulation loop does not end, can throw BlockingIOError here
            # Создали объектов
            num = nplaysers
            days = days
            peoples = []
            bank = Bank(assets=assets)
            url = url
            bank.get_token(url)
            inst_id = try_instrument(url, bank, inst_id)
            for i in range(num):
                email = "1bot" + str(i) + "@mail.ru"
                targetreturn = meantargetreturn * days / 365
                target = math.floor(
                    np.random.lognormal(np.log(targetreturn),
                                        .1 * targetreturn) * 1e4) / 1e4
                money = math.floor(
                    np.random.uniform(0.6 * meanmoney, 1.4 * meanmoney) *
                    1e4) / 1e4
                peoples.append(Person(email, target, money=money))
            get_tokens_or_create_user(url, peoples)
            for i in peoples:
                i.put_balance(url, inst_id)
            bank.put_balance(url, inst_id)

            emulate(url=url,
                    duration=days,
                    yearreturn=yearreturn,
                    bank=bank,
                    peoples=peoples,
                    inst_id=inst_id,
                    emulation_uuid=emulation_uuid)


if __name__ == '__main__':
    run_emulation(uuid.uuid4(),
                  url='http://localhost:8000/',
                  nplaysers=10,
                  meantargetreturn=5,
                  yearreturn=5)
