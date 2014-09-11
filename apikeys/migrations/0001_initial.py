# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Key'
        db.create_table(u'apikeys_key', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['backend.Person'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=16)),
            ('value', self.gf('django.db.models.fields.CharField')(unique=True, max_length=16)),
            ('enabled', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal(u'apikeys', ['Key'])

        # Adding model 'AuditLog'
        db.create_table(u'apikeys_auditlog', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('key', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['apikeys.Key'])),
            ('ts', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('key_enabled', self.gf('django.db.models.fields.BooleanField')()),
            ('remote_addr', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('request_method', self.gf('django.db.models.fields.CharField')(max_length=8)),
            ('absolute_uri', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'apikeys', ['AuditLog'])


    def backwards(self, orm):
        # Deleting model 'Key'
        db.delete_table(u'apikeys_key')

        # Deleting model 'AuditLog'
        db.delete_table(u'apikeys_auditlog')


    models = {
        u'apikeys.auditlog': {
            'Meta': {'object_name': 'AuditLog'},
            'absolute_uri': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['apikeys.Key']"}),
            'key_enabled': ('django.db.models.fields.BooleanField', [], {}),
            'remote_addr': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'request_method': ('django.db.models.fields.CharField', [], {'max_length': '8'}),
            'ts': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        u'apikeys.key': {
            'Meta': {'object_name': 'Key'},
            'enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['backend.Person']"}),
            'value': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '16'})
        },
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'backend.person': {
            'Meta': {'object_name': 'Person', 'db_table': "u'person'"},
            'bio': ('backend.models.TextNullField', [], {'null': 'True', 'blank': 'True'}),
            'cn': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'null': 'True'}),
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75'}),
            'expires': ('django.db.models.fields.DateField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'fd_comment': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'fpr': ('backend.models.FingerprintField', [], {'max_length': '40', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'mn': ('django.db.models.fields.CharField', [], {'max_length': '250', 'null': 'True', 'blank': 'True'}),
            'pending': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'sn': ('django.db.models.fields.CharField', [], {'max_length': '250', 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'status_changed': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow'}),
            'uid': ('backend.models.CharNullField', [], {'max_length': '32', 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['apikeys']