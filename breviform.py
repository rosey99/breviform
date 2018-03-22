
import subprocess
from subprocess import TimeoutExpired
import os
import sys
import json
#import tempfile
# support annotations
from typing import Sequence, Mapping, TypeVar, Any #generic types
from typing import Dict, Tuple, List #possibly required types

#from python_terraform.tfstate import Tfstate
import logging
logger = logging.getLogger(__name__)
# REMOVE for external logger config
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.setLevel(logging.DEBUG)
# a class for instrumentation. . .
class BreviForm:
    """
    Minimal wrapper for terraform CLI. 
    Supports the terraform commands init, plan, apply, and destroy only. 
    Basic usage:
        bf = BreviForm()
        p = bf.plan() #returns the path to plan, as a str
        r = bf.apply(p) # returns a tuple of 4 (quadtuple?)
          or 
        r = bf.apply() # uses the saved plan
      If you are not using a remote backend, maybe:
        s = bf.get_state() # gets the latest state as parsed json/dict
      And parse/persist it yourself.
      https://www.terraform.io/
    """
    ## set the default args for all commands, maybe make this settable later?
    __default_tf_args = ('-no-color', '-input=false')
    
    def __init__(self, tf_binpath: str='', tf_workdir: str='', tf_statepath: str='', output_map: dict={}):
        """
        Optionally supply:
          tf_binpath: a path to the terraform binary
          tf_workdir: path to a terraform working dir
          tf_statepath: path to an existing state file
          output_map: a dict of callables keyed by cmd: init, apply, etc.
        """
        # set default paths here
        apath = os.getcwd()
        self.tf_workdir = tf_workdir or apath
        self.tf_statepath = tf_statepath or os.path.join(self.tf_workdir, 'terraform.tfstate')
        self.tf_planpath = '' # pull this from tf args later
        # set the path to the terraform executable
        self.tf_binpath = tf_binpath or 'terraform'
        #set the output callable map
        self.output_map = output_map
        # dummy state state file, this gets replaced/updated depending on mthd
        self.tf_state = {}
        self.state_mtime = 0

    def tf_init(self, tfargs: Sequence, tf_workdir: str='') -> dict:
        """
        Runs terraform init with the supplied arguments.
        tfargs is a sequence of strings, and passed through unaltered.
        https://www.terraform.io/docs/commands/init.html
        """
        res = {}
        cmd = 'init'
        tf_args = self.__add_defaults(tfargs)
        # pass dummy vars for the cmdexec in this case
        r = self.tf_cmdexec(cmd, tfargs=tf_args, tfvars={}, tf_workdir=tf_workdir)
        res = self.format_result(cmd, r)
        return res
    
    def tf_plan(self, tfargs: Sequence, tfvars: Mapping, tf_workdir: str='') -> dict:
        """
        Runs terraform plan with supplied args
        At present the 'out' arg will be captured only, and is supplied by
        tfargs as one would from the CL.
        refer to https://www.terraform.io/docs/commands/plan.html
        
        """
        res = {}
        cmd = 'plan'
        extra_args = ['-detailed-exitcode']
        #get the default args for 'plan'
        tf_args = self.__add_defaults(tfargs, extra_args=extra_args)
        # exec
        r = self.tf_cmdexec(cmd, tfargs=tf_args, tfvars=tfvars, tf_workdir=tf_workdir)
        # format the results
        res = self.format_result(cmd, r)
        # did we save a plan?
        planpath = self.__get_tf_arg('-out=', r[3])
        wrkdir = tf_workdir or self.tf_workdir
        if planpath and not r[0] == 1: #detailed exitcode
            if not planpath.startswith('/'):
                planpath = os.path.join(wrkdir, planpath)
            self.tf_planpath = os.path.abspath(planpath) 
        # maybe load state, check args
        self.__maybe_set_state(r[3])
        logger.debug('Plan state path: %s', self.tf_statepath)
        return res

    def tf_apply(self, tfargs: Sequence, tfvars: Mapping, tf_workdir: str='') -> dict:
        """
        Runs terraform apply with the supplied args.
        
        refer to https://terraform.io/docs/commands/apply.html
        """
        res = {}
        cmd = 'apply'
        extra_args = ['-auto-approve']
        #get the default args for 'apply'
        tf_args = self.__add_defaults(tfargs, extra_args=extra_args)
        # exec
        r = self.tf_cmdexec(cmd, tfargs=tf_args, tfvars=tfvars, tf_workdir=tf_workdir)
        # format the results
        res = self.format_result(cmd, r)
        # grab the state file path if it was provided
        self.__maybe_set_state(r[3])
        logger.debug('Apply state path: %s', self.tf_statepath)
        return res

    def tf_destroy(self, tfargs: Sequence, tfvars: Mapping, tf_workdir: str='') -> dict:
        """
        Runs terraform destroy with the supplied args.

        refer to https://www.terraform.io/docs/commands/destroy.html
        """
        res = {}
        cmd = 'destroy'
        extra_args = ['-force']
        #get the default args for 'destroy'
        tf_args = self.__add_defaults(tfargs, extra_args=extra_args)
        # exec
        r = self.tf_cmdexec(cmd, tfargs=tf_args, tfvars=tfvars, tf_workdir=tf_workdir)
        # format the results
        res = self.format_result(cmd, r)
        # grab the state file path if it was provided
        self.__maybe_set_state(r[3])
        logger.debug('Destroy state path: %s', self.tf_statepath)
        return res
    
    def tf_output(self, tfargs: Sequence, tf_statepath: str='') -> dict:
        """
        https://www.terraform.io/docs/commands/output.html
        """
        statepath = tf_statepath or self.tf_statepath
        res = {}
        cmd = 'output'
        extra_args = ['-no-color', '-json', '-state={}'.format(statepath)]
        #get the default args for 'output'
        #tf_args = self.__add_defaults(tfargs, extra_args=extra_args)
        # exec
        r = self.tf_cmdexec(cmd, tfargs=extra_args, tfvars={})
        # format the results inline in this case
        try:
            rcode = r[0]
            logger.debug('Output returned: %s', rcode)
            if rcode == 0:
                res = json.loads(r[1])
            else:
                logger.warn('Output returned %s: Error: %s', rcode, str(r[2]))
        except Exception as e:
            logger.warn('Failed to load/parse terrform output command: %s', str(e))
        return res
         
    def tf_cmdexec(self, cmd: str, tfargs: Sequence, tfvars: Mapping, tf_workdir: str='') -> Tuple[int, str, str]:
        """
        Calls the terraform binary with the specified command.

        This method simply constructs the command string, and attempts to 
        execute it, and blocks while doing so.
          https://www.terraform.io/docs/commands/index.html
          https://www.terraform.io/guides/running-terraform-in-automation.html
        Any terraform variables passed in via tfargs (i.e., "-var user='USER'") as 
        a string are passed through unaltered, while variables 
        explicitly passed in are always converted to env vars for 
        the subprocess. Exposing potentially sensitive information via 
        command line args for a relatively long lived process is 
        discouraged, so passing all or most variables should be done 
        explicitly via tfvars. 
        """
        stderr = subprocess.PIPE
        stdout = subprocess.PIPE
        logger.info('command: %s %s', cmd, tfargs)
        work_dir = tf_workdir or self.tf_workdir
        evars = os.environ.copy()
        tfenv = self.__get_tf_env(tfvars)
        evars.update(tfenv)
        # make the command sting
        ## https://docs.python.org/3/library/subprocess.html#popen-constructor
        exeseq = [self.tf_binpath, cmd] + tfargs 
        try:
            p = subprocess.Popen(exeseq, stdout=stdout, stderr=stderr,
                cwd=work_dir, env=evars)
        except Exception as e:
            logger.warn('Command execution failed: %s', str(e))
            try:
                p.kill()
            except:
                pass
            return {} #for now
        # just messin' wit ya, we're making "progress"
        cnt=0
        out=''
        err=''
        ret_code=-1
        while True:    
            #we'll block here for now, possibly a hook for progress later?
            try:
                out, err = p.communicate(input=None, timeout=5)
            except TimeoutExpired:
                cnt += 5
                logger.warn('Your %s seconds are up!', cnt)
                continue
            except Exception as e:
                #catchall
                logger.warn('Terraform IPC failed: %s', e)
            break
        ret_code = p.returncode
        pargs = p.args
        logger.debug('stdout: {}'.format(out))
        logger.debug('stderr: {}'.format(err))
        logger.debug('return code: {}'.format(ret_code))
        logger.debug('With args: %s', str(pargs))
        # ~ if ret_code == 0:
            # ~ self.read_state_file()
        # ~ else:
            # ~ log.warn('error: {e}'.format(e=err))
        out = out.decode('utf-8')
        err = err.decode('utf-8')
        # return the args here for diagnostic and other reasons
        
        return ret_code, out, err, pargs

    ########### Helpers############
    @staticmethod
    def __get_tf_arg(argstr: str, arglist: Sequence) -> str:
        """
        Get a specific argument from the argslist.
        This is used to extract arguments after the 
        command has run (hopefully with success) typically 
        to get a file path for the plan or state.
        Returns an empty string on error or failure.
        """
        res = ''
        somepath = [ arg for arg in arglist if arg.startswith(argstr) ]
        if somepath:
            try:
                res = somepath[0].split('=')[-1]
                logger.debug('Extracted/fetched %s : %s', argstr, res)
            except Exception as e:
                logger.warn('Extracting path arg failed: %s', str(e))
        return res

    def __maybe_set_state(self, clargs: Sequence) -> bool:
        
        """
        As state in/out can be passed as CL args for tf_plan, tf_apply, 
        and tf_destroy, this helper checks args and updates the 
        state path, as well as sets the current state. 
        """
        res = False
        spath = ''
        # -state-out=PATH takes precedence as this is called after a run, 
        # but its value defaults to -state=PATH, and we are parsing args
        # as handed to the tf process
        spath = self.__get_tf_arg('-state-out=', clargs)
        spath = self.__get_tf_arg('-state=', clargs) or spath
        if not spath:
            spath = self.tf_statepath
        try:
            mtime = os.stat(spath).st_mtime
        except Exception as e:
            logger.warn('OS error for state path %s : %s', spath, str(e))
            return False #lazy?
        if mtime != self.state_mtime:
            newstate = self.load_state_file(spath)
            if newstate:
                self.tf_state = newstate
                logger.info('Updated with new state: %s', spath)
                self.state_mtime = mtime
                res = True 
        return res

    def __add_defaults(self, tfargs: Sequence, extra_args: list=[]) -> list:
        """
        Adds the/any default args if they are not present.
        Order is important, as the target dir/file path may be 
        the final arg, so we prepend.
        Extra args are extra defaults that may vary by command.
        """
        extra_args.extend(self.__default_tf_args)
        toadd = [ deft for deft in extra_args if deft not in tfargs ]
        logger.debug('Adding default args: %s', toadd)
        if tfargs: 
            toadd.extend(tfargs)  
        logger.debug('New args: %s', toadd)
        return toadd      
                
    @staticmethod
    def __get_tf_env(tfvars: Mapping):
        """
        A little helper to prefix keys for use in an ENV dict for 
        submission to os.popen as the env arg. Basically, prefixes each 
        key with 'TF_VAR_' per the docs:
          https://www.terraform.io/docs/configuration/variables.html#environment-variables
        This is really to help obscure any sensitive information that could 
        be revealed by CL args, and also to never write anything 
        sensitive to the fs, via history, for example.
        """
        return { ''.join(['TF_VAR_', k]):v for k,v in tfvars }
        
    def format_result(self, cmd, res):
            """
            Will look for a result formatter by module name, or use
            the default. Formats a dict suitable for serialization.
            Note when defining/calling external
            formatting callables, they must accept the following two
            args: 
                  cmd  str: init, apply, etc.
                  the result tuple[int, str, str, list] (quadtuple?)
                  which are ret_code, stdout, stderr, and passed args 
            This allows the user defined callable access to the entire
            runtime environment along with results.
            """
            modname = cmd
            form_func = self.output_map.get(modname)
            if form_func:
                return form_func(self, cmd, res)
            # by default, we move the invocation dict to the top
            # for easier access in our callback
            failed = False if not res[0] else True
            # we handle the special case of plan here, as it could get 
            # results back from a different formatter and
            # detailed_output is set to true
            failed = False if res[0] == 2 and cmd == 'plan' else failed
            invocd = {'modname':cmd, 'failed': failed, 'args': res[3]}
            result = dict(zip(['ret_code', 'output', 'errors'], res))
            return {'invocation': invocd, 'result': result }
            
    def load_state_file(self, path: str='') -> dict:
        """
        load a terraform state file
        takes a string as the path to a terraform state file,
        if path=='', then try self.tf_statepath 
        """
        tfstate = {}
        statepath = path or self.tf_statepath
        try:
            with open(statepath, 'r') as sfile:
                tfstate = sfile.read()
        except Exception as e:
            logger.warn('Failed to open/read terraform state file at: %s Err->%s', path, str(e))
        if tfstate:
            try:
                tfstate = json.loads(tfstate)
            except Exception as e:
                logger.warn('Failed to decode/load json: Err->%s', str(e))
        return tfstate

def runBreviForm(cmds: Sequence[str], tfargsmap: Mapping[str, Sequence], tfvars: Mapping[str, Any], tf_workdir: str) -> Tuple[int, Sequence]:
    """
    4 required args:
    cmds: sequence of 'tf_init', tf_plan, etc.
      these are BreviForm command methods, and they are not 
      renamed, so 'tf_apply' instead of 'apply'.
    tfargsmap: terraform command line arguments, 
      mapped to each command: probably defined in the upstream wf definition
      {'tf_plan': ['-out=MY_PLAN_PATH', ...] }
    tfvars: a mapping of variables, these are NEVER written
      to disk, and are passed in to the terraform process 
      as env vars
    tf_workdir: path to the working dir, passed
      on to terraform process as working dir 
    For integration hook
    1. Uses pre-built tf env dir
    2. Runs each command in the order provided
    """
    res = []
    failed = False
    ret_code = 0
    bf = BreviForm(tf_workdir=tf_workdir)
    for cmd in cmds:
        this_res = {}
        invocd = {'failed': False}
        emsg = ''
        try:
            meth = getattr(bf, cmd)
        except Exception as e:
            ret_code += 1
            emsg = str(e)
            failed = True
            logger.warn('Failed to resolve BreviForm method, error: %s', emsg)
        if not failed:
            tfargs = tfargsmap.get(cmd, [])
            try:
                # PITA. . .could be fixed by standardizing sigs
                if cmd == 'tf_init':
                    # different sig for now anyway
                    this_res['results'] = meth(tfargs=tfargs, tf_workdir=tf_workdir)
                elif cmd == 'tf_output':
                    this_res['results'] = meth(tfargs=tfargs)
                else:
                    this_res['results'] = meth(tfargs=tfargs, tfvars=tfvars, tf_workdir=tf_workdir)
            except Exception as e:
                ret_code += 1
                emsg = str(e)
                failed = True
                logger.warn('BreviForm command execution failed for command <%s>, error: %s', cmd, emsg)
        invocd['failed'] = failed
        invocd['errs'] = emsg
        this_res['invocation'] = invocd
        res.append(this_res)
        if failed: #ugh
            break
            
    return ret_code, res
    
