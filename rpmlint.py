#############################################################################
# File          : rpmlint.py
# Package       : rpmlint
# Author        : Frederic Lepied
# Created on    : Mon Sep 27 19:20:18 1999
# Version       : $Id$
# Purpose       : main entry point: process options, load the checks and run
#                 the checks.
#############################################################################

import sys
import AbstractCheck
import imp
import getopt
import Pkg
import Config
import os
import stat
import rpm
from Filter import *
import SpecCheck

version='@VERSION@'
policy=None

# Print usage information
def usage(name):
    print 'usage:', name, '[<options>] <rpm files|specfile>'
    print '  options in:'
    print '\t[-i|--info]\n\t[-I <error,error,>]\n\t[-c|--check <check>]\n\t[-a|--all]\n\t[-C|--checkdir <checkdir>]\n\t[-h|--help]\n\t[-v|--verbose]\n\t[-E|--extractdir <dir>]\n\t[-p|--profile]\n\t[-V|--version]\n\t[-n|--noexception]\n\t[-P|--policy <policy>]\n\t[-f|--file <config file to use instead of ~/.rpmlintrc>]'

# Print version information
def printVersion():
    print 'rpmlint version', version, 'Copyright (C) 1999-2007 Frederic Lepied, Mandriva'

# Load a python module from its file name
def loadCheck(name):
    (f, pathname, description) = imp.find_module(name, Config.checkDirs())
    imp.load_module(name, f, pathname, description)

#############################################################################
# main program
#############################################################################
def main():
    # Load all the tests
    for c in Config.allChecks():
        loadCheck(c)

    pkg=None
    try:
        # Loop over all file names given in arguments
        dirs=[]
        for f in args:
            pkgs = []
            isfile = False
            try:
                try:
                    st=os.stat(f)
                    isfile = True
                    if stat.S_ISREG(st[stat.ST_MODE]):
                        if not f.endswith(".spec"):
                            pkgs.append(Pkg.Pkg(f, extract_dir))
                        else:
                            # Short-circuit spec file checks
                            pkg = Pkg.FakePkg(f)
                            check = SpecCheck.SpecCheck()
                            check.check_spec(pkg, Pkg.readlines(f))
                            
                    elif stat.S_ISDIR(st[stat.ST_MODE]):
                        dirs.append(f)
                        continue
                    else:
                        raise OSError
                except OSError:
                    ipkgs = Pkg.getInstalledPkgs(f)
                    if not ipkgs:
                        sys.stderr.write(
                            'Error: no installed packages by name %s\n' % f)
                    else:
                        pkgs.extend(ipkgs)
            except KeyboardInterrupt:
                if isfile:
                    f = os.path.abspath(f)
                sys.stderr.write('Interrupted, exiting while reading %s\n' % f)
                sys.exit(2)
            except Exception, e:
                if isfile:
                    f = os.path.abspath(f)
                sys.stderr.write('Error while reading %s: %s\n' % (f, e))
                pkgs = []
                continue

            for pkg in pkgs:
                runChecks(pkg)
                pkg.cleanup()

        for d in dirs:
            try:
                for i in os.listdir(d):
                    f=os.path.abspath(os.path.join(d, i))
                    st=os.stat(f)
                    if stat.S_ISREG(st[stat.ST_MODE]):
                        if not (f.endswith('.rpm') or f.endswith('.spm') or \
                                f.endswith('.spec')):
                            continue
                        try:
                            if f.endswith('.spec'):
                                pkg = Pkg.FakePkg(f)
                                check = SpecCheck.SpecCheck()
                                check.check_spec(pkg, Pkg.readlines(f))
                            else:
                                pkg = Pkg.Pkg(f, extract_dir)
                                runChecks(pkg)
                        except KeyboardInterrupt:
                            sys.stderr.write('Interrupted, exiting while reading %s\n' % f)
                            sys.exit(2)
                        except Exception, e:
                            sys.stderr.write('Error while reading %s: %s\n' %
                                             (f, e))
                            pkg=None
                            continue
            except Exception, e:
                sys.stderr.write('Error while reading dir %s: %s' % (d, e))
                pkg=None
                continue

        # if requested, scan all the installed packages
        if all:
            try:
                if Pkg.v42:
                    ts=rpm.TransactionSet('/')
                    for item in ts.IDTXload():
                        pkg=Pkg.InstalledPkg(item[1][rpm.RPMTAG_NAME], item[1])
                        runChecks(pkg)
                else:
                    try:
                        db=rpm.opendb()
                        idx=db.firstkey()
                        while idx:
                            pkg=Pkg.InstalledPkg(db[idx][rpm.RPMTAG_NAME], db[idx])
                            runChecks(pkg)
                            idx=db.nextkey(idx)
                    finally:
                        del db
            except KeyboardInterrupt:
                sys.stderr.write('Interrupted, exiting while scanning all packages\n')
                sys.exit(2)

    finally:
        pkg and pkg.cleanup()


def runChecks(pkg):

    if verbose:
        printInfo(pkg, 'checking')

    for c in AbstractCheck.AbstractCheck.checks:
        c.check(pkg)

    pkg.cleanup()

#############################################################################
#
#############################################################################
sys.argv[0] = os.path.basename(sys.argv[0])

# parse options
try:
    (opt, args)=getopt.getopt(sys.argv[1:],
                              'iI:c:C:hVvp:anP:E:f:',
                              ['info',
                               'check=',
                               'checkdir=',
                               'help',
                               'version',
                               'verbose',
                               'profile',
                               'all',
                               'noexception',
                               'policy='
                               'extractdir=',
                               'file=',
                               ])
except getopt.error:
    print 'bad option'
    usage(sys.argv[0])
    sys.exit(1)

# process options
checkdir='/usr/share/rpmlint'
verbose=0
extract_dir=None
prof=0
all=0
conf_file='~/.rpmlintrc'
info_error=0

# load global config files
for f in ('/usr/share/rpmlint/config','/etc/rpmlint/config'):
    try:
        execfile(f)
    except IOError:
        pass
    except Exception, E:
        sys.stderr.write('Error loading %s, skipping: %s\n' % (f, E))
# pychecker fix
del f

# process command line options
for o in opt:
    if o[0] == '-c' or o[0] == '--check':
        Config.addCheck(o[1])
    elif o[0] == '-i' or o[0] == '--info':
        Config.info=1
    elif o[0] == '-I':
        info_error=o[1]
    elif o[0] == '-h' or o[0] == '--help':
        usage(sys.argv[0])
        sys.exit(0)
    elif o[0] == '-C' or o[0] == '--checkdir':
        Config.addCheckDir(o[1])
    elif o[0] == '-v' or o[0] == '--verbose':
        verbose=1
    elif o[0] == '-V' or o[0] == '--version':
        printVersion()
        sys.exit(0)
    elif o[0] == '-E' or o[0] == '--extractdir':
        extract_dir=o[1]
        Config.setOption('ExtractDir', extract_dir)
    elif o[0] == '-p' or o[0] == '--profile':
        prof=o[1]
    elif o[0] == '-n' or o[0] == '--noexception':
        Config.no_exception=1
    elif o[0] == '-P' or o[0] == '--policy':
        policy=o[1]
    elif o[0] == '-a' or o[0] == '--all':
        all=1
    elif o[0] == '-f' or o[0] == '--file':
        conf_file=o[1]
    else:
        print 'unknown option', o

# load user config file
try:
    execfile(os.path.expanduser(conf_file))
except IOError:
    pass
except Exception,E:
    sys.stderr.write('Error loading %s, skipping: %s\n' % (conf_file, E ))

if not extract_dir:
    extract_dir=Config.getOption('ExtractDir', '/tmp')

policy and Config.load_policy(policy)

if info_error:
    Config.info=1
    for c in Config.allChecks():
        loadCheck(c)
    for e in info_error.split(','):
        print "%s :" % e
        printDescriptions(e)
    sys.exit(0)

# if no argument print usage
if args == [] and not all:
    usage(sys.argv[0])
    sys.exit(0)

if prof:
    import profile
    import pstats
    profile.run('main()', prof)
    p = pstats.Stats(prof)
    p.print_stats('time').print_stats(20)
elif __name__ == '__main__':
    main()

# rpmlint.py ends here

# Local variables:
# indent-tabs-mode: nil
# py-indent-offset: 4
# End:
# ex: ts=4 sw=4 et
