from __future__ import with_statement
from os.path import expanduser, isdir
from fabric.api import *
from fabric.colors import red, green
from fabric.contrib import files
import urllib
import json


@task
def actionscript(script, script_params=None, getstr=False):
    with settings(warn_only=True):
        with cd('~/script'):
            if script_params:
                cmd = "python xdotool.py -a %s.json -v '%s'" % (script, urllib.urlencode(json.loads(script_params)))
            else:
                cmd = "python xdotool.py -a /home/pi/script/%s.json" % (script)

            if getstr:
                return cmd
            # result = run(cmd, pty=True)
            result = run(cmd)
            if result.failed:
                abort(red("%s command failed." % (script)))


@task
def dashcommand(command, screen_name=None, background=False, shouldkillX=False):
    with settings(warn_only=True):
        # local("git format-patch '%s^!' '%s' -o %s" % (rev, rev, patchdir))
        print("BEFORE: %s") % (command)
        # Escape single quotes
        command = command.replace("'", '"')
        print("AFTER : %s") % (command)
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
    with cd('~/script'):
        command = actionscript(script, script_params, True)
        # print("Running %s") % (command)
        dashcommand(command, screen_name, True)


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
def whatareu():
    resultd = {'ip': env.host}
    with hide('output'):
        result = run('hostname')
        if result.failed:
            abort(red("Failed to get hostname for %s." % (env.host)))
        else:
            resultd['name'] = result
        result = run('grep -o "kiosk.*" ~/.xinitrc | grep -v DASHBOARD')
        if result.failed:
            abort(red("Failed to get dashboards for %s." % (env.host)))
        else:
            resultd['dashboards'] = result
        print("%s") % (green(json.dumps(resultd)))


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


@task
def screenshot(width="889", height="600"):
    # Future version should mkdir -p local and remote screenshot directories
    if width.isdigit() and height.isdigit():
        remote_path = '/home/pi/screenshots'
        remote_file = "%s/current.png" % (remote_path)
        if not files.exists(remote_path):
            result = run('mkdir -p "%s"' % (remote_path))
            if result.failed:
                abort(red("Failed to make remote screenshot directory."))
        local_path = "%s/screenshots" % (expanduser("~"))
        local_file = "%s/%s.png" % (local_path, env.host)
        if not isdir(local_path):
            result = local('mkdir -p "%s"' % (local_path))
            if result.failed:
                abort(red("Failed to make local screenshot directory."))
        dashcommand("/usr/bin/raspi2png --pngname \"%s\" --width %d --height %d" % (remote_file, int(width), int(height)))
        get(remote_path=remote_file, local_path=local_file)
    else:
        print("Values for width and height must be integers")
