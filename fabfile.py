from __future__ import with_statement
from os.path import expanduser, isdir
from fabric.api import *
from fabric.colors import red, green
from fabric.contrib import files
from slugify import slugify
import urllib
import json
import os
import sys
from datetime import datetime
from fabric.contrib import django
from django.core.wsgi import get_wsgi_application
from django.core.exceptions import FieldError
from django.core.files.base import ContentFile


@task
def actionscript(script, script_params=None, getstr=False, nohup=False):
    with settings(warn_only=True):
        if script_params:
            if nohup:
                cmd = "cd ~/script/;nohup python xdotool.py -a %s.json -v '%s' >& /dev/null < /dev/null &" % (script, urllib.urlencode(json.loads(script_params)))
            else:
                cmd = "cd ~/script/;python xdotool.py -a %s.json -v '%s'" % (script, urllib.urlencode(json.loads(script_params)))
        else:
            cmd = "cd ~/script/;python xdotool.py -a %s.json" % (script)

        if getstr:
            return cmd

        if nohup:
            result = run(cmd, pty=False)
        else:
            result = run(cmd)
        if result.failed:
            abort(red("%s command failed." % (script)))


@task
def dashcommand(command, screen_name=None, background=False, shouldkillX=False):
    with settings(warn_only=True):
        # local("git format-patch '%s^!' '%s' -o %s" % (rev, rev, patchdir))
        # print("BEFORE: %s") % (command)
        # Escape single quotes
        command = command.replace("'", '"')
        # print("AFTER : %s") % (command)
        bg = ''
        if background:
            bg = '>/dev/null 2>&1 &'
        if screen_name:
            if shouldkillX:
                killX()
            cmd = "screen -S %s -X stuff '%s %s'`echo -ne '\015'`" % (screen_name, command, bg)
        else:
            cmd = command
        result = run(cmd)
    if result.failed:
        abort(red("Dashboard command failed."))


@task
def dashaction(screen_name, script, script_params=None):
    command = actionscript(script, script_params, True)
    # print("Running %s") % (command)
    dashcommand(command, screen_name, True)


@task
def refresh(exhosts=[]):
    exhosts = json.loads(exhosts)
    if exhosts:
        if any(env.host in s for s in exhosts):
            print(green("Excluding host %s" % (env.host)))
            return
    actionscript("refresh")


@task
def startRotate(exhosts=[]):
    exhosts = json.loads(exhosts)
    if exhosts:
        if any(env.host in s for s in exhosts):
            print(green("Excluding host %s" % (env.host)))
            return
    actionscript("rotatetab", '{"SLEEP":30,"TIMES":-1}', False, True)


@task
def launchX(envvars=None):
    dashcommand('unset ACTION', "Dashboard", shouldkillX=True)
    envdict = {}
    try:
        envdict = json.loads(urllib.unquote(envvars))
    except:
        print("Error parsing X parameters.")
    for k, v in envdict.iteritems():
        dashcommand('export %s="%s"' % (k, v), "Dashboard", shouldkillX=True)
    dashcommand("startx", "Dashboard", shouldkillX=True)


@task
def killX(xlock="/tmp/.X0-lock"):
    if files.exists(xlock):
        result = run("kill $(<'%s')" % (xlock))
        if result.failed:
            abort(red("Could not kill X."))
        else:
            if files.exists(xlock):
                run("rm -f '%s')" % (xlock))


@task
def launchyoutube(videoid=None):
    dashcommand("yt --player omxplayer", "Dashboard", shouldkillX=True)
    if videoid:
        dashcommand("s %s" % (videoid), "Dashboard")
        dashcommand("1", "Dashboard")


@task
def killyoutube():
    dashcommand("kill -9 $(pgrep omxplayer)")
    dashcommand("kill $(pgrep yt)")


@task
def install_packages(packages=None):
    # We should sanitize packages here of course
    # We should background the apt-get command and devise a strategy
    # to check the background task. Maybe loop and cat a text file
    # that apt-get redirects output until all background jobs exit.
    sudo("apt-get update -y")
    if packages:
        sudo("apt-get install -y %s" % (packages))


@task
def whatareu():
    hostinfo = {}
    with settings(warn_only=True):
        with hide('output'):
            # Check if facter is installed, and install if it isn't.
            result = run("which facter")
            if result.return_code != 0:
                print(red("Missing facter package.  Attempting to install"))
                install_packages(packages="facter")
            # Get System information
            result = run('facter --json')
            if result.failed:
                abort(red("Failed to get host data for %s." % (env.host)))
            else:
                hostinfo = json.loads(result)
            # Get Dashboard info
            result = run('awk \'/kiosk.*http/{s=""; for(i=4; i<=NF; i++) s=s $i " "; print s}\' ~/.xinitrc')
            if result.failed:
                print(red("Failed to get dashboards for %s." % (env.host)))
            else:
                hostinfo['dashboards'] = result.replace('"', '').split()
            print("%s") % (green(json.dumps(hostinfo, sort_keys=True, indent=4)))
            return hostinfo


@task
def nsslink(nssdir='/usr/lib/arm-linux-gnueabihf/nss', linkto='/usr/lib/nss'):
    result = sudo("ln -s %s/ %s" % (nssdir, linkto))
    if result.failed:
        abort(red("Failed to create link."))


@task
def reboot():
    result = sudo("reboot")
    if result.failed:
        abort(red("Failed to create link."))


def insertIntoGallery(
    gallery_title,
    gallery_slug,
    screenshot,
    title,
    slug,
    gallery_description="",
    gallery_tags="",
    caption="",
    tags="",
    fab_dir='%s/.fabric-bolt' % (os.path.expanduser('~/'))
):
    # Add custom fabric-bolt settings directory
    sys.path.insert(0, fab_dir)
    # Utilize django within fabfile
    # Load custom fabric-bolt settings file
    django.settings_module('settings')
    # Loads the django Models
    get_wsgi_application()
    # Once loaded we can reference them
    from photologue.models import Photo
    from photologue.models import Gallery

    file = open(screenshot, 'rb')
    data = file.read()

    # First Generate or Retrieve the Photo Model and save or update it
    try:
        photo = Photo.objects.get(slug=slug)
        photo.date_added = datetime.now()
        photo.date_taken = datetime.now()
        print("~~~ FOUND existing Screenshot ~~~")
    except Photo.DoesNotExist:
        photo = Photo(title=title, slug=slug, caption=caption, is_public=True, tags=tags,)
        print("~~~ CREATED new Screenshot ~~~")

    try:
        photo.image.save(os.path.basename(screenshot), ContentFile(data))
    except FieldError:
        # For some reason a field, 'photo,' is being passed to model as a field.
        pass
    print("~~~ SAVED Screenshot ~~~")

    # Now Create or Retrieve the named Gallery and add the photo to it.
    gallery = None
    try:
        gallery = Gallery.objects.get(title=gallery_title)
        print("~~~ FOUND existing Screenshot Gallery ~~~")
    except Gallery.DoesNotExist:
        gallery = Gallery(title=gallery_title, slug=gallery_slug, description=gallery_description, is_public=True, tags=gallery_tags,)
        gallery.save()
        print("~~~ CREATED new Screenshot Gallery ~~~")

    if gallery:
        gallery.photos.add(photo)
        print("~~~ Added Screenshot to Gallery ~~~")
        print("<a target=\"_parent\" href=\"/photologue/gallery/%s\">View Screenshot Gallery %s</a>") % (gallery_title, gallery_title)

    # Reset the syspath
    sys.path.remove(fab_dir)


@task
def screenshot(width="1440", height="810", ratio="75"):
    with settings(warn_only=True):
        if width.isdigit() and height.isdigit():
            # Define remote image path and file
            remote_path = '/home/%s/screenshots' % (env.user)
            remote_file = "%s/current.png" % (remote_path)
            # Check for raspi2png
            screenshotcmd = "/usr/bin/raspi2png --pngname \"%s\" --width %d --height %d" % (remote_file, int(width), int(height))
            result = run("which raspi2png")
            if result.return_code != 0:
                # If not using raspi2png we use scrot, which gnerates a thumb file
                remote_thumb_file = "%s/current-thumb.png" % (remote_path)
                screenshotcmd = "export DISPLAY=:0 && /usr/bin/scrot -t %d \"%s\" && mv '%s' '%s'" % (int(ratio), remote_file, remote_thumb_file, remote_file)

            # Make remote directories if they don't already exist
            if not files.exists(remote_path):
                result = run('mkdir -p "%s"' % (remote_path))
                if result.failed:
                    abort(red("Failed to make remote screenshot directory."))

            # Define local image path
            local_path = "%s/screenshots" % (expanduser("~"))

            # Define a global gallery for Web Interface
            gallery_title = "ALL"
            if hasattr(env, 'group'):
                # If this stage contains a group, change the storage path and gallery to the group
                local_path = "%s/%s" % (local_path, env.group)
                gallery_title = env.group
            # Define local image path
            local_file = "%s/%s.png" % (local_path, env.host)

            # Make local directories if they don't already exist
            if not isdir(local_path):
                result = local('mkdir -p "%s"' % (local_path))
                if result.failed:
                    abort(red("Failed to make local screenshot directory."))

            # Take Remote Screenshot
            dashcommand(screenshotcmd)
            # Copy screenshot to central system
            result = get(remote_path=remote_file, local_path=local_file)
            if result.failed:
                    abort(red("Failed to download screenshot."))
            # Remove remote file
            run("rm %s" % (remote_file))
            print(green("Downloaded screenshot to %s" % (local_file)))
            # Generate a photo title from local file name
            screenshot_title = os.path.splitext(os.path.basename(local_file))[0]
            # Insert photo into gallery.
            insertIntoGallery(
                gallery_title=gallery_title,
                gallery_slug=slugify(gallery_title),
                screenshot=local_file,
                title=screenshot_title,
                slug=slugify(screenshot_title),
            )
        else:
            print("Values for width and height must be integers")
