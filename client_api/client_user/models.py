import uuid
from enum import Enum

import pyotp
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.db.utils import DataError
from django.utils import timezone


def generate_referral_code(length):
    d = uuid.uuid4()
    str = d.hex
    return str[:int(length)]


class Currency(models.Model):
    title = models.CharField(max_length=30, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.title}'


class UserManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The given email must be set')
        with transaction.atomic():
            user = self.model(email=self.normalize_email(email),
                              **extra_fields)
            user.set_password(password)
            user.save()
            # TODO HARDCODE USD
            user.assign_fiat_balance('USD')
            user.assign_instrument_balance()

            return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        return self._create_user(email, password=password, **extra_fields)


class ClientUserStatus(Enum):
    VERIFIED = 'verified'
    UNVERIFIED = 'unverified'


class ClientUser(AbstractBaseUser):
    created_at_dt = models.DateTimeField(auto_now_add=True)
    updated_at_dt = models.DateTimeField(auto_now=True)
    email = models.EmailField(max_length=40, unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=128,
                              choices=[(tag.name, tag.value)
                                       for tag in ClientUserStatus],
                              default=ClientUserStatus.UNVERIFIED.value)
    is_active = models.BooleanField(default=True)
    password_changed_at_dt = models.DateTimeField(default=timezone.now)
    totp_token = models.CharField(max_length=30, blank=True)
    is_email_verified = models.BooleanField(default=False)
    email_verified_at_dt = models.DateTimeField(null=True, blank=True)
    email_verification_code = models.UUIDField(default=uuid.uuid4)
    is_only_view_allowed = models.BooleanField(default=False)
    comment = models.CharField(max_length=500, default='', blank=True)
    language = models.CharField(max_length=5, default='en', blank=True)
    country = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, default='', blank=True)
    is_superuser = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'

    @property
    def is_staff(self):
        return self.is_superuser

    def change_is_active(self, is_active):
        self.is_active = is_active
        self.save(update_fields=['is_active'])

    def has_perm(self, perm, obj=None):
        return self.is_staff and settings.DEBUG

    def has_module_perms(self, app_label):
        return self.is_staff and settings.DEBUG

    def get_two_factor_qr_url(self):
        if not self.totp_token:
            self.generate_totp_token()
        qr_url = pyotp.totp.TOTP(self.totp_token).provisioning_uri(
            self.email, issuer_name=settings.TWO_FACTOR_ISSUER)
        return qr_url

    def generate_totp_token(self):
        self.totp_token = pyotp.random_base32()
        self.save(update_fields=['totp_token'])

    def assign_fiat_balance(self, currency_name):
        try:
            currency = Currency.objects.get(title=currency_name)
        except ObjectDoesNotExist:
            currency = Currency.objects.create(title=currency_name)
        FiatBalance.objects.create(user=self, currency=currency)

    def assign_instrument_balance(self):
        for instrument in Instrument.objects.all():
            InstrumentBalance.objects.create(instrument=instrument, user=self)


class InstrumentBalance(models.Model):
    user = models.ForeignKey(ClientUser, on_delete=models.PROTECT)
    instrument = models.ForeignKey('Instrument', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=20, decimal_places=8, default=0)

    def __str__(self):
        return f'{self.amount} {self.instrument}'


class FiatBalance(models.Model):
    user = models.ForeignKey(ClientUser, on_delete=models.PROTECT)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=20, decimal_places=8, default=0)

    def __str__(self):
        return f'{self.amount} {self.currency}'


class InstrumentStatus(Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    DELETED = 'deleted'


class Instrument(models.Model):
    # TODO Create instrument balance for every user when instrument is created
    name = models.CharField(max_length=50)
    status = models.CharField(max_length=30,
                              choices=[(tag.name, tag.value)
                                       for tag in InstrumentStatus],
                              default=InstrumentStatus.ACTIVE.value)
    # these ones for underlying credit
    credit_created_at_d = models.DateField(null=True)
    credit_expires_at_d = models.DateField(null=True)
    # expected values like 15.575 %
    credit_interest_percentage = models.DecimalField(max_digits=5,
                                                     decimal_places=3,
                                                     null=True)
    created_at_dt = models.DateTimeField(auto_now_add=True)
    updated_at_dt = models.DateTimeField(auto_now=True)

    def save(self,
             force_insert=False,
             force_update=False,
             using=None,
             update_fields=None):
        if not self.pk:
            super().save(force_insert, force_update, using, update_fields)
            self.assign_balances(self.pk)
        else:
            super().save(force_insert, force_update, using, update_fields)

    def assign_balances(self, instrument_id):
        for user in ClientUser.objects.all():
            InstrumentBalance.objects.get_or_create(
                user=user,
                instrument_id=instrument_id,
                defaults={
                    'user': user,
                    'instrument_id': instrument_id
                })

    def __str__(self):
        return self.name


class OrderType(Enum):
    SELL = 'sell'
    BUY = 'buy'


class OrderStatus(Enum):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    DELETED = 'deleted'


class Order(models.Model):
    type = models.CharField(max_length=15,
                            choices=[(tag.name, tag.value)
                                     for tag in OrderType])
    status = models.CharField(max_length=30,
                              choices=[(tag.name, tag.value)
                                       for tag in OrderStatus],
                              default=OrderStatus.ACTIVE.value)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    actual_price = models.DecimalField(max_digits=20,
                                       decimal_places=8,
                                       null=True)
    instrument = models.ForeignKey(Instrument,
                                   on_delete=models.PROTECT,
                                   related_name='instrument')
    total_sum = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    remaining_sum = models.DecimalField(max_digits=20,
                                        decimal_places=8,
                                        default=0)
    created_at_dt = models.DateTimeField(auto_now_add=True)
    updated_at_dt = models.DateTimeField(auto_now=True)
    # num of seconds in which order expires
    expires_in = models.PositiveIntegerField()
    user = models.ForeignKey(ClientUser, on_delete=models.PROTECT)

    def __str__(self):
        return f'[{self.type}|{self.instrument}] @{self.price} ({self.remaining_sum}/{self.total_sum})'

    @classmethod
    def _trade_orders(cls, first: 'Order', second: 'Order') -> (
            'Order',
            'Order',
            InstrumentBalance,
            InstrumentBalance,
            FiatBalance,
            FiatBalance,
    ):
        """
        Internal method that actually trades orders
        """
        # TODO Add fee
        with transaction.atomic():
            trade_amount = min(first.remaining_sum, second.remaining_sum)
            first_balance = InstrumentBalance.objects.select_for_update().get(
                user=first.user, instrument=first.instrument)
            second_balance = InstrumentBalance.objects.select_for_update().get(
                user=second.user, instrument=first.instrument)
            first_fiat_balance = FiatBalance.objects.select_for_update().get(
                user=first.user)
            second_fiat_balance = FiatBalance.objects.select_for_update().get(
                user=second.user)
            if not first_balance:
                raise ValueError(
                    f'Balance for user {first.user} in instrument not found')
            if not second_balance:
                raise ValueError(
                    f'Balance for user {second.user} in instrument not found')
            if first.type == OrderType.BUY.value and first_fiat_balance.amount < trade_amount * second.price:
                raise ValueError(
                    f'Not enough funds for {first_fiat_balance.user}')
            if first.type == OrderType.SELL.value and second_fiat_balance.amount < trade_amount * second.price:
                raise ValueError(
                    f'Not enough funds for {second_fiat_balance.user}')
            if first.type == OrderType.BUY.value and second_balance.amount < trade_amount:
                raise ValueError(
                    f'Not enough instrument balance for {second_balance.user}')
            if first.type == OrderType.SELL.value and first_balance.amount < trade_amount:
                raise ValueError(
                    f'Not enough instrument balance for {first_balance.user}')
            first.remaining_sum -= trade_amount
            second.remaining_sum -= trade_amount
            if first.type == OrderType.BUY.value:
                first_balance.amount += trade_amount
                second_balance.amount -= trade_amount
                first_fiat_balance.amount -= trade_amount * second.price
                second_fiat_balance.amount += trade_amount * second.price
            else:
                first_balance.amount -= trade_amount
                second_balance.amount += trade_amount
                first_fiat_balance.amount += trade_amount * second.price
                second_fiat_balance.amount -= trade_amount * second.price
            if first.remaining_sum == 0:
                first.status = OrderStatus.COMPLETED.value
                first.actual_price = second.price
            if second.remaining_sum == 0:
                second.status = OrderStatus.COMPLETED.value
                second.actual_price = second.price
            return first, second, first_balance, second_balance, first_fiat_balance, second_fiat_balance

    @classmethod
    def place_order(cls, order: 'Order') -> 'Order':
        """
        Places order into orderbook
        """
        counter_order_type = OrderType.SELL.value if order.type == OrderType.BUY.value else OrderType.BUY.value
        counter_orders = None
        with transaction.atomic():
            if counter_order_type == OrderType.SELL.value:
                counter_orders = cls.objects.select_for_update().filter(
                    type=counter_order_type,
                    instrument=order.instrument,
                    price__lte=order.price).order_by('price', 'created_at_dt')
            elif counter_order_type == OrderType.BUY.value:
                counter_orders = cls.objects.select_for_update().filter(
                    type=counter_order_type,
                    instrument=order.instrument,
                    price__gte=order.price).order_by('-price', 'created_at_dt')
            if not counter_orders:
                # place order into the order book
                order.save()
                return order
            for counter_order in counter_orders:
                order, counter_order, *balances = cls._trade_orders(
                    order, counter_order)
                order.save()
                counter_order.save()
                for balance in balances:
                    balance.save()
                if order.status == OrderStatus.COMPLETED:
                    return order
        return order

    @classmethod
    def get_avg_price(cls, instrument: Instrument) -> float:
        """
        Returns volume weighted price
        :param instrument:
        :return:
        """
        try:
            avg_price = cls.objects.filter(
                instrument=instrument,
                # status=OrderStatus.COMPLETED.value
            ).annotate(price_t_volume=models.F('price') *
                       models.F('total_sum')).aggregate(
                           avg_price=models.Sum('price_t_volume') /
                           models.Sum('total_sum'))
        except DataError:  # handle division by zero
            return 0
        return float(avg_price.get('avg_price', 0) or 0)

    @classmethod
    def get_liquidity_rate(cls, instrument: Instrument) -> float:
        """
        Returns liquidity rate weighted by order volume
        :param instrument:
        :return:
        """
        completed_volume = cls.objects.filter(
            instrument=instrument,
            status=OrderStatus.COMPLETED.value).aggregate(
                models.Sum('total_sum')).get('total_sum__sum', 0)
        rate = cls.objects.filter(instrument=instrument).aggregate(
            rate=completed_volume / models.Sum('total_sum'))
        return float(rate.get('rate', 0) or 0)

    @classmethod
    def get_placed_assets_rate(cls, instrument: Instrument) -> float:
        """
        Returns number of tokens "bank" user has
        :param instrument:
        :return:
        """
        bank_balance = InstrumentBalance.objects.filter(
            user__email__contains='bank',
            instrument=instrument).order_by('user__created_at_dt').last()
        if bank_balance:
            return float(bank_balance.amount)
        return 0


class OrderPriceHistory(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.DO_NOTHING)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    created_at_dt = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField()


class LiquidityHistory(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.DO_NOTHING)
    value = models.DecimalField(max_digits=20, decimal_places=5)
    created_at_dt = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField()


class PlacedAssetsHistory(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.DO_NOTHING)
    value = models.DecimalField(max_digits=20, decimal_places=5)
    created_at_dt = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField()
