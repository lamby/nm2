# file:///usr/share/doc/fabric/html/tutorial.html

from fabric.api import local, run, sudo, cd, env
import git

env.hosts = ["nono.debian.org"]

def prepare_deploy():
    #local("./manage.py test my_app")
    #local("git add -p && git commit")
    local("test `git ls-files -cdmu | wc -l` = 0")
    local("git push")

def deploy():
    prepare_deploy()
    repo = git.Repo()
    current_commit = repo.head.commit.hexsha

    deploy_dir = "/srv/nm.debian.org/nm2"
    with cd(deploy_dir):
        sudo("git fetch", user="nm")
        sudo("test `git show-ref -s origin/master` = " + current_commit, user="nm")
        sudo("./manage.py collectstatic --noinput", user="nm")
        sudo("./manage.py migrate", user="nm")
        sudo("psql service=nm -c 'grant select,insert,update,delete on all tables in schema public to nmweb'",
             user="nm")
        sudo("psql service=nm -c 'grant usage on all sequences in schema public to nmweb'", user="nm")
        sudo("touch nm2/wsgi.py", user="nm")
