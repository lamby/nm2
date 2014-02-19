from django.shortcuts import redirect

def logout(request):
    if request.user.is_authenticated():
        return redirect("/cgi-bin/dacs/dacs_signout")
    else:
        return redirect("https://sso.debian.org/sso/logout")

