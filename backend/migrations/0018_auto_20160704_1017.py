# -*- coding: utf-8 -*-


from django.db import migrations, models

def fill_email_ldap(apps, schema_editor):
    Person = apps.get_model("backend", "Person")
    #robot = Person.objects.get(username="__housekeeping__")
    for person in Person.objects.all():
        person.email_ldap = person.email
        person.save()
        #person.save(audit_notes="Initialized email_ldap from existing email field", audit_author=robot)


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0017_person_email_ldap'),
    ]

    operations = [
        migrations.RunPython(fill_email_ldap),
    ]
