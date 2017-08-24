from django.utils.timezone import now, utc
from django.db import transaction
from backend import const
from process.email import notify_new_dd
from . import models as bmodels
import contextlib
import datetime
import logging
import json

log = logging.getLogger(__name__)


class OperationField:
    def __init__(self, null=False, default=None):
        self.cls_name = None
        self.name = None
        self.null = null
        self.default = default

    def get_default(self):
        if self.null is False:
            raise TypeError("{}() missing required argument: {}".format(self.cls_name, self.name))

        if callable(self.default):
            return self.default()
        else:
            return self.default


class StringField(OperationField):
    def validate(self, val):
        if val is None: return val
        return str(val)

    def to_json(self, val):
        return val


class BooleanField(OperationField):
    def validate(self, val):
        if val is None: return val
        return bool(val)

    def to_json(self, val):
        return val


class DateField(OperationField):
    def validate(self, val):
        if val is None: return val
        if isinstance(val, datetime.date): return val
        val = datetime.datetime.strptime(val, "%Y-%m-%d")
        return val.date()

    def to_json(self, val):
        if val is None: return val
        if val.tzinfo: val = val.astimezone(utc)
        return val.strftime("%Y-%m-%d")


class DatetimeField(OperationField):
    def validate(self, val):
        if val is None: return val
        if isinstance(val, datetime.datetime): return val
        val = datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        val = val.replace(tzinfo=utc)
        return val

    def to_json(self, val):
        if val is None: return val
        if val.tzinfo: val = val.astimezone(utc)
        return val.strftime("%Y-%m-%d %H:%M:%S")


class PersonField(OperationField):
    def validate(self, val):
        if val is None: return val
        if isinstance(val, bmodels.Person):
            return val
        else:
            return bmodels.Person.lookup(val)

    def to_json(self, val):
        if val is None: return val
        return val.lookup_key


class AMField(OperationField):
    def validate(self, val):
        if val is None: return val
        if isinstance(val, bmodels.AM):
            return val
        else:
            return bmodels.AM.lookup(val)

    def to_json(self, val):
        if val is None: return val
        return val.lookup_key


class PersonStatusField(OperationField):
    def validate(self, val):
        if val is None: return val
        if val not in const.ALL_STATUS_BYTAG:
            raise ValueError("{} is not a valid status for a person".format(val))
        return val

    def to_json(self, val):
        return val


class FingerprintField(OperationField):
    def validate(self, val):
        if val is None: return val
        # TODO: validate as hex string, remove spaces, deal with backend.Fingerprint
        return str(val)

    def to_json(self, val):
        return val


class OperationMeta(type):
    def __new__(cls, cls_name, bases, attrs):
        fields = {}

        # Populate fields with all the fields of base classes
        for base in bases:
            base_fields = getattr(base, "fields", None)
            if base_fields is None: continue
            fields.update(base_fields)

        # Move all class members that are an instance of OperationField to the
        # fields dict
        for name, attr in tuple(attrs.items()):
            if not isinstance(attr, OperationField): continue
            field = attrs.pop(name)
            field.cls_name = cls_name
            field.name = name
            fields[name] = field

        attrs["fields"] = fields
        return super().__new__(cls, cls_name, bases, attrs)


class Operation(metaclass=OperationMeta):
    classes = {}
    _test_collect = None

    audit_author = PersonField()
    audit_notes = StringField()
    audit_time = DatetimeField(null=True, default=now)

    def __init__(self, **kw):
        self.fields_null = set()

        for name, field in self.fields.items():
            if name not in kw:
                setattr(self, name, field.get_default())
                self.fields_null.add(name)
            else:
                setattr(self, name, field.validate(kw.get(name)))

    def set_field(self, name, value):
        """
        Set `self.<name>` to value, validating value using the relevant field.
        """
        setattr(self, name, self.fields[name].validate(value))

    def set_null_field(self, name, value):
        """
        Set `self.<name>` to value, validating value using the relevant field.

        It does nothing if a value for `name` was provided at construction
        time.
        """
        if name not in self.fields_null: return
        self.fields_null.remove(name)
        self.set_field(name, value)

    def to_dict(self):
        """
        Returns a dict with all the constructor arguments to recreate this
        operation
        """
        res = {}
        for name, field in self.fields.items():
            res[name] = field.to_json(getattr(self, name))
        return res

    def to_json(self, **kw):
        res = self.to_dict()
        res["Operation"] = self.__class__.__name__
        return json.dumps(res, **kw)

    def execute(self, request=None):
        if self._test_collect is not None:
            self._mock_execute()
            self._test_collect.append(self)
            return

        with transaction.atomic():
            self._execute()
        self.notify(request)

    def _mock_execute(self, request=None):
        """
        This gets run instead of _execute and notify when _test_collect is
        active
        """
        pass

    def notify(self, request=None):
        """
        Send email notifications after the operation has been performed.

        `request` can be provided to render site urls in the email.
        """
        # By default, do nothing
        pass

    @classmethod
    @contextlib.contextmanager
    def test_collect(cls):
        """
        While this context manager is in use, all Operation.execute() calls
        will just append self to a list and exit without doing anything.

        This can be used to test if a view would have executed the right
        operation, testing the actual side effects separately.
        """
        orig_target = cls._test_collect
        cls._test_collect = []
        yield cls._test_collect
        cls._test_collect = orig_target

    @classmethod
    def register(cls, _class):
        cls.classes[_class.__name__] = _class
        return _class

    @classmethod
    def from_json(cls, encoded):
        import process.ops as pops
        val = json.loads(encoded)
        _class = val.pop("Operation")
        Op = cls.classes[_class]
        return Op(**val)


@Operation.register
class CreatePerson(Operation):
    username = StringField()
    cn = StringField()
    mn = StringField(null=True, default="")
    sn = StringField(null=True, default="")
    email = StringField()
    status = PersonStatusField()
    fpr = FingerprintField(null=True)
    last_login = DatetimeField(null=True)
    date_joined = DatetimeField(null=True)
    created = DatetimeField(null=True)
    expires = DateField(null=True)

    def __str__(self):
        return "Create user {}".format(self.email)

    def _execute(self):
        kw = {
            "status_changed": self.audit_time,
        }
        for name in self.fields:
            if name in ("fpr", "audit_time"): continue
            kw[name] = getattr(self, name)

        p = bmodels.Person.objects.create_user(**kw)
        if self.fpr:
            fpr = p.fprs.create(
                fpr=self.fpr,
                is_active=True,
                audit_author=self.audit_author,
                audit_notes=self.audit_notes,
            )


@Operation.register
class ChangeStatus(Operation):
    person = PersonField()
    status = PersonStatusField()
    
    def __str__(self):
        return "Change status of {} to {}".format(self.person.lookup_key, self.status)

    def _execute(self):
        import process.models as pmodels
        process = pmodels.Process.objects.create(
            person=self.person,
            applying_for=self.status,
            frozen_by=self.audit_author,
            frozen_time=self.audit_time,
            approved_by=self.audit_author,
            approved_time=self.audit_time,
            closed_by=self.audit_author,
            closed_time=self.audit_time,
            skip_requirements=True,
        )
        process.add_log(
            changed_by=self.audit_author,
            logtext=self.audit_notes,
            is_public=False,
            action="proc_approve",
            logdate=self.audit_time
        )
        self.person.status = self.status
        self.person.status_changed = self.audit_time
        self.person.save(
            audit_author=self.audit_author,
            audit_notes=self.audit_notes)


@Operation.register
class ChangeFingerprint(Operation):
    person = PersonField()
    fpr = FingerprintField()

    def __str__(self):
        return "Change fingerprint of {} to {}".format(self.person.lookup_key, self.fpr)

    def _execute(self):
        fpr = self.person.fprs.create(
            fpr=self.fpr, is_active=True,
            audit_author=self.audit_author,
            audit_notes=self.audit_notes)
