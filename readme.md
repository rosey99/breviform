breviform
========

Breviform is a python 3.5+ version of terraform automation. At the 
moment breviform has no external dependencies save terraform itself.

This is an effort to automate terraform using python, and in so doing, 
eliminate CLI dependence while automating capture and inspection of 
results. By and large, terraform plays along well with external automation 
efforts, as the API is open and flexible. Potential benefits include:

  * Upstream fetching/decryptiion of artifacts (e.g., vars, certs)
  * Integration with a workflow system such as Celery Canvas
  * Integration of multiple tools (e.g., terraform, fabric/fybre and ansible/misible) in a single process 
  * Use breviform in support of a stateful, immutable infrastructure model

This work is largely based on the terraform-python project, but aims to be 
smaller, and leave all administration and maintenance of the 
terraform runtime environment to another tool, or a human. Many thanks to 
the devs over there for their efforts:

   [python-terraform](https://github.com/beelit94/python-terraform)
 
Breviform removes python 2 compatibility, along with most of the 
command logic that is not essential to the basic work of creating, 
modifying, and destroying infrastructure. Similar to other 
automation projects based on Fabric3, and Ansible, I decided that I 
needed/wanted a tool that does only one thing, as well as possible.
Conceptually, this could be combined with Ansible/Minsible and/or Fabric/Fybre as part 
of state-driven workflow, regardless of where the target systems reside. 
A related project includes the celery runtime configuration and tasks 
required to run breviform inside a celery worker, which itself can run in a 
docker container.

As far as thread-safety goes, terraform wants its own process space, and 
while running breviform in a threaded environment may work great, 
it has not been tested. The typical use case would be to run breviform for 
each target (AWS, VMWare, Openstack) and each image or system profile, and 
then run Minsible and/or Fybre over one or more subsets of the 
created hosts in an end-to-end, automated process. For an idea of what is 
possible, have a look at [flowmastah-artifact](https://github.com/rosey99/flowmastah-artifact) which contains workflow for 
the related python/celery project called "flowmastah." 

Simple Openstack example configurations are located in the "terraform" 
directory of flowmastah-artifact.

Flowmastah-artifact is used in development and testing of the flowmastah 
project (ongoing, pre-release), and demonstrates a state-driven workflow 
configuration, that itself relies on git for versioning of artifacts as well 
as workflow configuration which is. . .Just another artifact, after all.

 
"Brevi" means small, humble, or brief. Hopefully, all three.


Getting Started
---------------

- Install python 3.5+ if it is not installed, or create a python 3.5+ virtual envirnment.

    `python3 -m venv env`

- Clone or download source directory from git, you may need to install git if not already installed.  

- Activate your virtual environment.

    `source env/bin/activate`

- Upgrade packaging tools.

    `env/bin/pip install --upgrade pip setuptools`

- Install the project in editable mode.

    `env/bin/pip install -e PATH_TO_BREVIFORM_DIR`

- Enter the root directory of your python virtual environment.

    `cd env`

- Create your terraform working directory. If you don't know what this is:

    [Terraform Site](https://www.terraform.io/)
    
- Run init, plan, apply, and output. . .By firing up python, and:

    `>>> from breviform.breviform import runBreviForm as rBF`
    
    `>>> tf_workdir='PATH/TO/TF_WORKING_DIR'`
    
    `>>> r = rBF(cmds=['tf_plan', 'tf_apply', 'tf_output'], tfargsmap={}, tfvars={}, tf_workdir=tf_workdir)`
    
- Or:
    `>>> r = rBF(cmds=['tf_plan', 'tf_apply', 'tf_output'], tfargsmap={}, tfvars={'count': 3}, tf_workdir=tf_workdir)`
    
- And of course:
    
    `>>> r = rBF(cmds=['tf_destroy'], tfargsmap={}, tfvars={}, tf_workdir=tf_workdir)`

Terraform supports a large number of arguments when invoked from the command line, and 
breviform attempts to supply defaults that are sensible when doing away with the CLI.  


Enjoy!
