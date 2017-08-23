from django.contrib.sites.shortcuts import get_current_site

def build_absolute_uri(location, request=None):
    if request is not None:
        return request.build_absolute_uri(location)
    site = get_current_site(request)
    return "https://{}{}".format(site.domain, location)

