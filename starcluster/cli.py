#!/usr/bin/env python
"""
starcluster [<global-opts>] action [<action-opts>] [<action-args> ...]
"""

__description__ = """
StarCluster - (http://web.mit.edu/starcluster)
Please submit bug reports to starcluster@mit.edu
"""

__moredoc__ = """
Each command consists of a class, which has the following properties:

- Must have a class member 'names' which is a list of the names for the command;

- Can optionally have a addopts(self, parser) method which adds options to the
  given parser. This defines command options.
"""

__version__ = "$Revision: 0.9999 $"
__author__ = "Justin Riley <justin.t.riley@gmail.com>"

import os
import sys
import time
from pprint import pprint, pformat
from starcluster import cluster
from starcluster import config
from starcluster import exception
from starcluster import static
from starcluster import optcomplete
CmdComplete = optcomplete.CmdComplete

from starcluster.logger import log

#try:
    #import optcomplete
    #CmdComplete = optcomplete.CmdComplete
#except ImportError,e:
    #optcomplete, CmdComplete = None, object

class CmdBase(CmdComplete):
    parser = None
    opts = None
    gopts = None

    @property
    def goptions_dict(self):
        return dict(self.gopts.__dict__)

    @property
    def options_dict(self):
        return dict(self.opts.__dict__)

    @property
    def specified_options_dict(self):
        """ only return options with non-None value """
        specified = {}
        options = self.options_dict
        for opt in options:
            if options[opt]:
                specified[opt] = options[opt]
        return specified

    @property
    def cfg(self):
        return self.goptions_dict.get('CONFIG')

class CmdStart(CmdBase):
    """Start a new cluster """
    names = ['start']

    @property
    def completer(self):
        if optcomplete:
            try:
                cfg = config.StarClusterConfig()
                cfg.load()
                return optcomplete.ListCompleter(cfg.get_cluster_names())
            except Exception, e:
                log.error('something went wrong fix me: %s' % e)

    def addopts(self, parser):
        opt = parser.add_option("-x","--no-create", dest="NO_CREATE",
            action="store_true", default=False, help="Do not launch new ec2 \
instances when starting cluster (uses existing instances instead)")
        parser.add_option("-l","--login-master", dest="LOGIN_MASTER",
            action="store_true", default=False, 
            help="ssh to ec2 cluster master node after launch")
        parser.add_option("-t","--tag", dest="CLUSTER_TAG",
            action="store", type="string", default=time.strftime("%Y%m%d%H%M"), 
            help="tag to identify cluster")
        parser.add_option("-d","--description", dest="CLUSTER_DESCRIPTION",
            action="store", type="string", 
            default="Cluster requested at %s" % time.strftime("%Y%m%d%H%M"), 
            help="brief description of cluster")
        parser.add_option("-s","--cluster-size", dest="CLUSTER_SIZE",
            action="store", type="int", default=None, 
            help="number of ec2 nodes to launch")
        parser.add_option("-u","--cluster-user", dest="CLUSTER_USER",
            action="store", type="string", default=None, 
            help="name of user to create on cluster (defaults to sgeadmin)")
        opt = parser.add_option("-S","--cluster-shell", dest="CLUSTER_SHELL",
            action="store", choices=static.AVAILABLE_SHELLS.keys(),
            default=None, help="shell for cluster user ")
        if optcomplete:
            opt.completer = optcomplete.ListCompleter(opt.choices)
        parser.add_option("-m","--master-image-id", dest="MASTER_IMAGE_ID",
            action="store", type="string", default=None, 
            help="image to use for master")
        parser.add_option("-n","--node-image-id", dest="NODE_IMAGE_ID",
            action="store", type="string", default=None, 
            help="image to use for node")
        opt = parser.add_option("-i","--instance-type", dest="INSTANCE_TYPE",
            action="store", choices=static.INSTANCE_TYPES.keys(),
            default=None, help="specify machine type for cluster")
        if optcomplete:
            opt.completer = optcomplete.ListCompleter(opt.choices)
        parser.add_option("-a","--availability-zone", dest="AVAILABILITY_ZONE",
            action="store", type="string", default=None, 
            help="availability zone to launch ec2 instances in ")
        parser.add_option("-k","--keyname", dest="KEYNAME",
            action="store", type="string", default=None, 
            help="name of AWS ssh key to use for cluster")
        parser.add_option("-K","--key-location", dest="KEY_LOCATION",
            action="store", type="string", default=None, metavar="FILE",
            help="path to ssh key used for this cluster")
        parser.add_option("-v","--volume", dest="VOLUME",
            action="store", type="string", default=None, 
            help="EBS volume to attach to master node")
        parser.add_option("-D","--volume-device", dest="VOLUME_DEVICE",
            action="store", type="string", default=None, 
            help="Device label to use for EBS volume")
        parser.add_option("-p","--volume-partition", dest="VOLUME_PARTITION",
            action="store", type="string", default=None, 
            help="EBS Volume partition to mount on master node")

    def execute(self, args):
        if not args:
            self.parser.error("please specify a cluster")
        cfg = self.cfg
        for cluster_name in args:
            try:
                scluster = cfg.get_cluster(cluster_name)
                scluster.update(self.specified_options_dict)
                #pprint(scluster)
            except exception.ClusterDoesNotExist,e:
                log.warn(e.explain())
                aws_environ = cfg.get_aws_credentials()
                cluster_options = self.specified_options_dict
                kwargs = {}
                kwargs.update(aws_environ)
                kwargs.update(cluster_options)
                scluster = cluster.Cluster(**kwargs)
            if scluster.is_valid():
                scluster.start(create=not self.opts.NO_CREATE)
                #log.info('valid cluster')
            else:
                log.error('not valid cluster')

class CmdStop(CmdBase):
    """Shutdown a running cluster"""
    names = ['stop']
    def execute(self, args):
        if not args:
            self.parser.error("please specify a cluster")
        cfg = self.cfg
        for cluster_name in args:
            cluster.stop_cluster(cluster_name, cfg)

class CmdSshMaster(CmdBase):
    """SSH to a cluster's master node"""
    names = ['sshmaster']
    def execute(self, args):
        if not args:
            self.parser.error("please specify a cluster")
        for arg in args:
            cluster.ssh_to_master(arg, self.cfg)

class CmdSshNode(CmdBase):
    """SSH to a cluster node"""
    names = ['sshnode']
    def execute(self, args):
        if not args:
            self.parser.error("please specify a cluster and node to connect to")
        elif len(args) == 1:
            scluster = args[0]
            if scluster.startswith("ec2-"):
                cluster.ssh_to_node(scluster, self.cfg)
                return
            self.parser.error("please specify a node to connect to")
        scluster = args[0]
        nodes = args[1:]
        for node in nodes:
            cluster.ssh_to_cluster_node(scluster, node, self.cfg)

class CmdListClusters(CmdBase):
    """List all active clusters"""
    names = ['listclusters']
    def execute(self, args):
        cfg = self.cfg
        cluster.list_clusters(cfg)

class CmdCreateAmi(CmdBase):
    """Create a new image (AMI) from a currently running EC2 instance"""
    names = ['createami']
    def execute(self, args):
        log.error('unimplemented')
        #pprint(args)
        #pprint(self.gopts)
        #pprint(self.opts)

class CmdCreateVolume(CmdBase):
    """Create a new EBS volume for use with StarCluster"""
    names = ['createvolume']
    def execute(self, args):
        log.error('unimplemented')
        #pprint(args)
        #pprint(self.gopts)
        #pprint(self.opts)

class CmdListImages(CmdBase):
    """List all registered EC2 images (AMIs)"""
    names = ['listimages']
    def execute(self, args):
        ec2 = self.cfg.get_easy_ec2()
        ec2.list_registered_images()

class CmdListBuckets(CmdBase):
    """List all S3 buckets"""
    names = ['listbuckets']
    def execute(self, args):
        s3 = self.cfg.get_easy_s3()
        buckets = s3.list_buckets()

class CmdShowImage(CmdBase):
    """Show all files on S3 for an EC2 image (AMI)"""
    names = ['showimage']
    def execute(self, args):
        if not args:
            self.parser.error('please specify an AMI id')
        ec2 = self.cfg.get_easy_ec2()
        for arg in args:
            ec2.list_image_files(arg)
   
class CmdShowBucket(CmdBase):
    """Show all files in a S3 bucket"""
    names = ['showbucket']
    def execute(self, args):
        if not args:
            self.parser.error('please specify a S3 bucket')
        for arg in args:
            s3 = self.cfg.get_easy_s3()
            bucket = s3.list_bucket(arg)

class CmdRemoveImage(CmdBase):
    """Deregister an EC2 image (AMI) and remove it from S3"""
    names = ['removeimage']
    def execute(self, args):
        log.error('unimplemented')
        #pprint(args)
        #pprint(self.gopts)
        #pprint(self.opts)

class CmdListInstances(CmdBase):
    """List all running EC2 instances"""
    names = ['listinstances']
    def execute(self, args):
        ec2 = self.cfg.get_easy_ec2()
        ec2.list_all_instances()

class CmdHelp:
    """Show StarCluster usage"""
    names =['help']
    def execute(self, args):
        import optparse
        if args:
            cmdname = args[0]
            try:
                sc = subcmds_map[cmdname]
                lparser = optparse.OptionParser(sc.__doc__.strip())
                if hasattr(sc, 'addopts'):
                    sc.addopts(lparser)
                lparser.print_help()
            except KeyError:
                raise SystemExit("Error: invalid command '%s'" % cmdname)
        else:
            gparser.parse_args(['--help'])

def get_description():
    return __description__.replace('\n','',1)

def parse_subcommands(gparser, subcmds):

    """Parse given global arguments, find subcommand from given list of
    subcommand objects, parse local arguments and return a tuple of global
    options, selected command object, command options, and command arguments.
    Call execute() on the command object to run. The command object has members
    'gopts' and 'opts' set for global and command options respectively, you
    don't need to call execute with those but you could if you wanted to."""

    import optparse
    global subcmds_map # needed for help command only.

    print get_description()

    # Build map of name -> command and docstring.
    subcmds_map = {}
    gparser.usage += '\n\nAvailable Actions\n'
    for sc in subcmds:
        gparser.usage += '- %s: %s\n' % (', '.join(sc.names),
                                       sc.__doc__.splitlines()[0])
        for n in sc.names:
            assert n not in subcmds_map
            subcmds_map[n] = sc

    # Declare and parse global options.
    gparser.disable_interspersed_args()

    gopts, args = gparser.parse_args()
    if not args:
        gparser.print_help()
        raise SystemExit("\nError: you must specify an action.")
    subcmdname, subargs = args[0], args[1:]

    # load StarClusterConfig into global options
    cfg = config.StarClusterConfig(gopts.CONFIG)
    cfg.load()
    gopts.CONFIG = cfg

    # Parse command arguments and invoke command.
    try:
        sc = subcmds_map[subcmdname]
        lparser = optparse.OptionParser(sc.__doc__.strip())
        if hasattr(sc, 'addopts'):
            sc.addopts(lparser)
        sc.parser = lparser
        sc.gopts = gopts
        sc.opts, subsubargs = lparser.parse_args(subargs)
    except KeyError:
        raise SystemExit("Error: invalid command '%s'" % subcmdname)

    return gopts, sc, sc.opts, subsubargs

def main():
    # Create global options parser.
    global gparser # only need for 'help' command (optional)
    import optparse
    gparser = optparse.OptionParser(__doc__.strip(), version=__version__)
    gparser.add_option("-d","--debug", dest="DEBUG", action="store_true",
        default=False,
        help="print debug messages (useful for diagnosing problems)")
    gparser.add_option("-c","--config", dest="CONFIG", action="store",
        metavar="FILE",
        help="use alternate config file (default: ~/.starclustercfg)")

    # Declare subcommands.
    subcmds = [
        CmdStart(),
        CmdStop(),
        CmdListClusters(),
        CmdSshMaster(),
        CmdSshNode(),
        CmdListInstances(),
        CmdListImages(),
        CmdShowImage(),
        CmdRemoveImage(),
        CmdListBuckets(),
        CmdShowBucket(),
        CmdCreateAmi(),
        CmdCreateVolume(),
        CmdHelp(),
    ]

    # subcommand completions
    scmap = {}
    for sc in subcmds:
        for n in sc.names:
            scmap[n] = sc
  
    if optcomplete:
        listcter = optcomplete.ListCompleter(scmap.keys())
        subcter = optcomplete.NoneCompleter()
        optcomplete.autocomplete(
            gparser, listcter, None, subcter, subcommands=scmap)
    elif 'COMP_LINE' in os.environ:
        return -1

    gopts, sc, opts, args = parse_subcommands(gparser, subcmds)
    sc.execute(args)

def test():
    pass

if os.environ.has_key('starcluster_commands_test'):
    test()
elif __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print "Interrupted, exiting."
