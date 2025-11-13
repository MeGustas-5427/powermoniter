from __future__ import annotations

from enum import IntEnum
from uuid import uuid7

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser
from django.db import models


class UserManager(BaseUserManager):
    """仅提供 createsuperuser，满足管理命令需求。"""

    use_in_migrations = True

    def create_superuser(self, username: str, password: str | None = None, **extra_fields):
        if not username:
            raise ValueError("Superuser must define a username")
        if not password:
            raise ValueError("Superuser must define a password")

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.password_hash = user.password
        user.save(using=self._db)
        return user


class DeviceStatus(IntEnum):
    """设备状态枚举。"""
    ENABLED = 1
    DISABLED = 0

    @classmethod
    def choices(cls):
        names = {cls.ENABLED: 'enabled', cls.DISABLED: 'disabled'}
        return [(member.value, names[member]) for member in cls]


class IngressType(IntEnum):
    """采集入口类型。"""
    MQTT = 0
    TCP = 1

    @classmethod
    def choices(cls):
        names = {cls.MQTT: 'mqtt', cls.TCP: 'tcp'}
        return [(member.value, names[member]) for member in cls]


class User(AbstractBaseUser):

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    username = models.CharField(max_length=150, unique=True, verbose_name="用户名")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    is_staff = models.BooleanField(default=False, verbose_name="是否为管理员")
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    last_login_at = models.DateTimeField(null=True, blank=True, verbose_name="最后登录时间")
    pw_fail_count = models.PositiveSmallIntegerField(default=0, verbose_name="输入密码错误次数")

    objects = UserManager()
    USERNAME_FIELD = "username"
    # REQUIRED_FIELDS = ["username"]

    class Meta:
        app_label = "repositories"
        db_table = "account_user"

    # 为了兼容Django admin，添加权限相关方法（可选）
    def has_perm(self, perm, obj=None):
        """用户是否有特定权限"""
        # 这里您可以实现自定义权限逻辑
        return self.is_staff

    def has_module_perms(self, app_label):
        """用户是否有访问某个app的权限"""
        # 这里您可以实现自定义权限逻辑
        return self.is_staff


class Device(models.Model):
    """设备实体，按 MAC 管理采集入口配置。"""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    name = models.CharField(max_length=100, verbose_name="设备名称")
    location = models.CharField(max_length=200, verbose_name="设备所在地方")
    mac = models.CharField(max_length=12, unique=True)
    broker = models.CharField(max_length=100, verbose_name="服务器地址")
    port = models.PositiveSmallIntegerField(default=1883)
    pub_topic = models.CharField(max_length=100, verbose_name="发布主题")
    sub_topic = models.CharField(max_length=100, verbose_name="订阅主题")
    client_id = models.CharField(max_length=100)
    username = models.CharField(max_length=100, verbose_name="用户名参数")
    password = models.CharField(max_length=100, verbose_name="密码参数")
    status = models.BooleanField(choices=DeviceStatus.choices(), default=DeviceStatus.ENABLED)
    collect_enabled = models.BooleanField(default=False)
    description = models.CharField(max_length=255, null=True)
    ingress_type = models.BooleanField(choices=IngressType.choices(), default=IngressType.MQTT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(
        "User",
        db_constraint=False,
        related_name="devices",
        null=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        app_label = "repositories"
        db_table = "device"

    def _default_ingress_config(self) -> dict[str, object]:
        return {
            "name": self.name,
            "location": self.location,
            "broker": self.broker,
            "port": self.port,
            "pub_topic": self.pub_topic,
            "sub_topic": self.sub_topic,
            "topic": self.sub_topic,
            "client_id": self.client_id,
            "username": self.username,
            "password": self.password,
        }

    @property
    def ingress_config(self) -> dict[str, object]:
        cached = getattr(self, "_ingress_config_cache", None)
        if cached is None:
            cached = self._default_ingress_config()
            self._ingress_config_cache = cached
        return cached

    @ingress_config.setter
    def ingress_config(self, value: dict[str, object] | None) -> None:
        self._ingress_config_cache = value or {}


class Reading(models.Model):
    """用电量读数实体，记录幂等信息。"""

    device = models.ForeignKey(
        "Device",
        db_constraint=False,
        related_name="readings",
        on_delete=models.CASCADE,
    )
    mac = models.CharField(max_length=12)
    ts = models.DateTimeField(null=True, blank=True, verbose_name='记录时间')
    energy_kwh = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="累计用电量，单位KW*H，保留三位小数，断电后不会归零，重置后会归零")
    power = models.DecimalField(max_digits=12, decimal_places=4, null=True, verbose_name="当前功率，单位W，保留三位小数")
    voltage = models.DecimalField(max_digits=8, decimal_places=3, null=True, verbose_name="当前电压，单位V，保留三位小数")
    current = models.DecimalField(max_digits=8, decimal_places=3, null=True, verbose_name="当前电流，单位A，保留三位小数")
    key = models.CharField(max_length=64, null=True, verbose_name="设备通断电状态，0：断电，1：通电")
    payload = models.JSONField()
    ingested_at = models.DateTimeField(auto_now_add=True)
    payload_hash = models.CharField(max_length=64)

    class Meta:
        app_label = "repositories"
        db_table = "reading"
        unique_together = ["mac", "ts", "payload_hash"]
        indexes = [models.Index(fields=["device", "ts"]),]


class DeadLetter(models.Model):
    """死信记录，用于追踪解析失败的报文。"""

    device = models.ForeignKey(
        "Device",
        db_constraint=False,
        related_name="dead_letters",
        null=True,
        on_delete=models.SET_NULL,
    )
    mac = models.CharField(max_length=12, null=True, db_index=True)
    raw_payload = models.JSONField()
    failure_reason = models.CharField(max_length=255)
    occured_at = models.DateTimeField(auto_now_add=True)
    retryable = models.BooleanField(default=False)
    meta = models.JSONField(null=True)

    class Meta:
        app_label = "repositories"
        db_table = "dead_letter"


class SubscriptionCheckpoint(models.Model):
    """订阅进度检查点。"""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    device = models.OneToOneField(
        "Device",
        db_constraint=False,
        related_name="checkpoint",
        on_delete=models.CASCADE,
    )
    mac = models.CharField(max_length=12, db_index=True, verbose_name="设备 MAC")
    last_envelope_ts = models.DateTimeField(null=True, verbose_name="最近一次处理的消息时间戳")
    cursor = models.CharField(max_length=128, null=True, verbose_name="自定义游标（比如 MQTT 消息 ID、TCP 偏移量等）")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="进度更新时间")

    class Meta:
        app_label = "repositories"
        db_table = "subscription_checkpoint"
