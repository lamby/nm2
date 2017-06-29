# coding: utf-8





class DbRouter(object):
    def db_for_read(self, model, **hints):
        if model._meta.app_label == "projectb":
            return "projectb"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == "projectb":
            return 'projectb'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "projectb" or app_label == "projectb":
            return False
