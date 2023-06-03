# found in the LICENSE file.
import os
import sys
import argparse
import re
import atexit
import signal
import yaml
import datetime
import subprocess
import pprint
import jinja2
from string import Template
from functools import partial
from typing import List, Optional, Sequence, Union

from chromite.lib import commandline
from chromite.lib import portage_util
from chromite.lib import cros_build_lib

pprint = pprint.PrettyPrinter()
# repos for ebuild files
CHROMIUMOS_OVERLAY = (
    "/home/chrome/chromiumos/src/third_party/chromiumos-overlay"
)
PORTAGE_STABLE = "/home/chrome/chromiumos/src/third_party/portage-stable"
# profile directory
CHROMEOS_TARGET_PROFILES_ROOT = f"{CHROMIUMOS_OVERLAY}/profiles/target/chromeos"
# controls debug logging
DEBUG = False
CLEAN = False
# each entry to modified/failed is
# {"package": "net-libs/etc", "path": "full/path/to/ebuild"}
# if modified, add "use_flag": "flag"
# patterns for parsing the ebuild
patterns = {}
patterns["start_declaration"] = re.compile('[\w\d\-\_]+\+?="')
patterns["start_quote"] = re.compile('"\s*')
patterns["end_quote"] = re.compile(r'.*"')
patterns["depend"] = re.compile('\w*?DEPEND\+?="')
patterns["atom"] = re.compile("^[^\s]+\/[^\s]+$")
patterns["flag"] = re.compile("^(\!|\+|\-)?[A-Za-z0-9\-_]+\??$")
patterns["use"] = re.compile("(I|COMMON_)?USE\+?=")
patterns["toggleable_flag"] = re.compile("[\w\d\-_]+\?")
patterns["var"] = re.compile("\$\{[\w\d\-\._]+\}")
patterns["package"] = re.compile("((>=)?[\w\d\.\-]+\/?[\w\d\.-]+(:=)?)")
patterns["comment"] = re.compile("#.*?$")
patterns["virtual"] = re.compile("virtual\/.+")
patterns["inclusive_or"] = re.compile(re.escape("||"))
patterns["exclusive_or"] = re.compile(re.escape("^^"))
patterns["at_most"] = re.compile(re.escape("??"))

patterns["atom_modifiers"] = {}
patterns["atom_modifiers"]["version"]=re.compile("([\-](\d{1,3})\.?(\d{1,3})?\.?(\d{1,3})?\*?)")
patterns["atom_modifiers"]["slot"]=re.compile("(:(\d{1,3})?\=)")
patterns["atom_modifiers"]["subslot"]=re.compile("(:\d{1.3)(?=\/)")
patterns["atom_modifiers"]["revision"]=re.compile("([\-_]r[a-zA-Z]*\d*)")
patterns["atom_modifiers"]["atom_prefix"]=re.compile("^[\>\=\<!]{1,4}")
patterns["atom_modifiers"]["conditional"]=re.compile("\[.+\]")

patterns["flag_modifiers"]={}
patterns["flag_modifiers"]["prefix"]=re.compile("^[~\+\-]{1,2}")
patterns["flag_modifiers"]["optional"]=re.compile("\?$")

report = jinja2.Template(
    """
attempting to remove: {[ original_package }}

The following atoms will be added to `package.mask`
{% for p in package_masks %}
  - {{ p  }}
{% endfor %}

The following atoms will be added to package.use.mask`
{% for p in package_use_masks %}
  - {{ p[0] }} {{ p[1] }}
{% endfor %}

The following packages cannot be removed automatically:
{% for p in nonoptional_dependencies %}
  - {{ p }}
{% endfor %}

"""
)


def zprint(s: str, debug: bool = False):
    if all([DEBUG, debug]):
        print(s)
    if not debug:
        print(s)


def get_parser() -> commandline.ArgumentParser:
    """Build the argument parser."""
    parser = commandline.ArgumentParser(description=__doc__)

    parser.add_argument("-p", "--package", help="Package.", required=True)
    parser.add_argument(
        "--vbose", action="store_true", help="debug logging", default=False
    )
    parser.add_argument("--sysroot", type="path", help="Sysroot path.")
    return parser


def run_subprocess(cmd: str) -> str:
    """
    a convenience method for running ```subprocess.run()```

    Parameters:
    -----------
    cmd: str
        the string command

    Returns
    -------
    str
        the result of the subprocess
    """
    zprint(cmd, True)
    res = None
    res = cros_build_lib.run(
        cmd, shell=True, capture_output=True, encoding="utf-8"
    )
    if res:
        return res.stdout
    return res


def prompt_yn(prompt):
    while True:
        print(prompt)
        choice = input("Enter yes or no (y/n): ").lower()
        if choice in ["yes", "y"]:
            return True
        elif choice in ["no", "n"]:
            return False
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

def prompt_selection(selections):
    num=len(selections)
    while True
        print("Choose one of the following")
        for i,s in enumerate(selections):
            print(f"{i+1}. {s}")
        choice=int(input("Choice [0-9]: ")) -1
        if choice <= num:
            return selections[choice]
        else:
            print("Invalid selection")

def get_temporary_filehandle(file_):
    fullpath_ = os.path.abspath(file_)
    path_, f_ = os.path.split(fullpath_)
    temp = f"~{f_}"
    return (fullpath_, f"{path_}/{temp}")


def make_temporary_file(file_):
    orig, temp = get_temporary_filehandle(file_)
    with open(orig, "rb") as existing:
        with open(temp, "wb") as new:
            new.write(existing.read())


def write_temporary_file(file_):
    orig, temp = get_temporary_filehandle(file_)
    if not os.path.exists(temp):
        raise Exception(f"no temporary file for {orig} available")
    try:
        with open(temp, "rb") as new:
            with open(orig, "wb") as existing:
                existing.write(new.read())
        os.remove(temp)
    except:
        raise


def read_content(filepath):
    content = ""
    with open(filepath, "r") as fh:
        content += fh.read()
    return content



def tokenize(string):
    tokens = string.replace("\n", "").replace('"', " ").split(" ")
    tokens = [x for x in tokens if x != ""]
    return tokens


def add_package_mask(package, version=""):
    """
    adds an entry to the package.mask file at chromiumos-overlay/profiles/target/chromeos/
    """
    global CHROMEOS_TARGET_PROFILES_ROOT, OUTPUT
    fh = f"{CHROMEOS_TARGET_PROFILES_ROOT}/~package.mask"
    # check to see if the package is already masked
    cmd = "cat ${fh} | grep {package}"
    res = run_subprocess(cmd)
    if res:
        zprint(
            f"not adding the package: {package} to package.mask,  it already exists",
            debug=True,
        )
        return
    else:
        package_string = ""
        package_string += f"{package}"
        if version:
            package_string += f":{version}"
        cmd = f"echo {package_string} >> {fh}"
    run_subcommand(cmd)


def add_package_use_mask(package, use_flag, version=""):
    """
    adds an entry to the package.use.mask file at chromiumos-overlay/profiles/target/chromeos/

    """
    global CHROMEOS_TARGET_PROFILES_ROOT, OUTPUT
    fh = f"{CHROMEOS_TARGET_PROFILES_ROOT}/~package.use.mask"
    ebuild_path = equery_which(package)
    # check to see if the package is already masked
    cmd = f"grep -n  {package} {fh}"
    res = run_subprocess(cmd)
    if res:
        line, orig = res.split("\n").split(":")
        add = prompt_yn(
            f"the package {package} is already specified in the use mask file: {line}, {orig} -- edit existing file to add a new use mask?"
        )
        if add:
            zprint(
                f"editing the existing mask the package:{package}", debug=True
            )
            new = orig + f"{use_flag}"
            cmd = f"sed s/orig/{new}/g {fh}"
            run_subprocess(cmd)
        else:
            zprint(
                f"not adding to the existing mask - add this mask manually",
                debug=True,
            )
            OUTPUT["failed"].append(
                {
                    "package": package,
                    "ebuild_path": ebuild_path,
                    "use_flag": use_flag,
                }
            )

    else:
        package_string = ""
        package_string += f"{package}"
        if version:
            package_string += f":{version}"
        cmd = f"echo {package_string} >> {fh}"
    run_subcommand(cmd)
    OUTPUT["modified"].append(
        {"package": package, "ebuild_path": ebuild_path, "use_flag": use_flag}
    )


class Task:
    def __init__(self, task, **kwargs):
        self.task = task
        self.kwargs = kwargs

    def run_task(self):
        if self.task == "pm":
            add_package_mask(self.kwargs["package"])
        if self.task == "pum":
            add_package_use_mask(self.kwargs["package"], self.kwargs["useflag"])
        if self.task == "mtf":
            make_temporary_file(self.kwargs["file_"])
        if self.task == "wtf":
            write_temporary_file(self.kwargs["file_"])


def get_atom_name(package_str, 
                  filepath=False):
    package={}
    package={"fullname": package_str}
    for k,v  in patterns["atom_modifiers"].items():
        try:
            _m=v.search(package_str)
        except:
            print(package_str)
            raise
        if _m:
            package_str=re.sub(v,"",package_str)
            package[k]=_m.group(0)
    package["atom"]=package_str
    if filepath:
        path=equery_which(package_str)
        return package, path
    else:
        return package

def get_flag_name(flag_str):
    flag={}
    flag["full"]=flag_str
    for k,v in patterns["flag_modifiers"].items():
        _m=v.search(flag_str)
        if _m:
            flag_str=re.sub(v,"",flag_str)
            if k == "optional":
                flag[k]=True
            else:
                flag[k]=_m.group(0)
    flag["name"]=flag_str
    return flag

class UseFlag:
    def __init__(self, flag):
        flag=get_flag_name(flag)
        self.name=flag.get("name")
        self.optional=flag.get("optional")
        prefix=flag.get("prefix",[])
        self.original=flag.get("full")
        if prefix:
            prefix=list(prefix)    
        self.enabled = True if "+" in prefix else False
        self.disabled = True if "-" in prefix  else False
        self.testing = True if "~" in prefix else False
        self.default = True if not any([self.enabled, self.disabled]) else False
        self.toggle = True if self.optional else False
        self.condition = ""

    def set_condition(self, condition):
        """
        a useflag can be set as the state of another useflag

        e.g. if useflag1? ( -useflag2 )
        """
        self.condition=condition


    def __str__(self):
        return self.original

    def can_toggle(self):
        """
        a UseFlag is only toggleable in the context of the package in which it's declared.
        e.g. a flag in package X can be optional, but in Y can be required

        Thus, UseFlag objects can only be used in the context of a package, and not individually
        as singletons
        """
        self.toggle = True

    def match(self, string):
        if re.match(string, self.name):
            return True


class Package:
    p_use = re.compile("(I|REQUIRED_)?USE")
    p_depend = re.compile("(B|C|R|P|[\w]+)_?(DEP)(END)?")

    def __init__(self, name, parse_ebuild=False):
        self.fullname = name
        package, filepath=get_atom_name(name, filepath=True)
        self.filepath = filepath
        # get the name of the package without versioning/revisions
        self.name=package["atom"]
        self.dependencies = []
        self.useflags = []
        self.metadata = None
        if not self.filepath:
            return
        if self.filepath is not None and parse_ebuild:
            self._parse_ebuild()
    def print_ebuild(self):
        content = read_content(self.filepath)
        print(content)

    def get_use_flags(self):
        return [str(x) for x in self.useflags]

    def get_dependencies(self, return_packages=False):
        deps= {"nonoptional": []}
        print(self.dependencies)
        for d in self.dependencies:
            if d.useflag:
                if d.useflag.name  not in deps.keys():
                    deps[d.useflag.name] = []
                if return_packages:
                    deps[d.useflag.name].append(d)
                else:
                    deps[d.useflag.name].append(d.name)
            else:
                if return_packages:
                    deps["nonoptional"].append(d)
                else:
                    deps["nonoptional"].append(d.name)

        return deps       
    def _parse_ebuild(self):
        """
        parses an ebuild file - adds all dependencies
        to `self.dependencies`

        adds all useflags to `self.useflags`

        rather than use the built in `equery` tool, this reads the content directly and uses
        regex to parse the pattern
        """
        ebuild_raw = read_content(self.filepath).replace("\t", " ")
        ebuild=ebuild_raw.split)("\n")
        metadata = {}
    }
        
        for i in range(0, len(ebuild)):
            # filter comments
            line = patterns["comment"].sub("", ebuild[i])
            match_sd = patterns["start_declaration"].search(line)
            if match_sd:
                declaration = (
                    match_sd.group(0).replace('="', "").replace("+", "")
                )
                s_idx = i
                e_idx = i
                content = patterns["start_declaration"].sub("", line)
                match_end = patterns["end_quote"].match(content)
                while not match_end:
                    e_idx += 1
                    content += ebuild[e_idx]
                    match_end = patterns["end_quote"].match(ebuild[e_idx])

                if Package.p_depend.match(declaration):
                    i, tokens, e =self._set_dependencies(tokenize(content))
                    if e:
                        print(i)
                        print(tokens)
                        print(e)
                elif Package.p_use.match(declaration):
                    if declaration=="REQUIRED_USE":
                        self._set_required_use(tokenize(content))
                    else:
                        self._set_useflags(tokenize(content))
                metadata[declaration] = content
        for k, v in metadata.items():
            if k in dir(self):
                attr = getattr(self, k)
                attr += v
                setattr(self, k, v)
            else:
                setattr(self, k, v)
        self.metadata = metadata

    def _add_dependency(self, d):
        if d.name not in [x.name for x in self.dependencies]:
            self.dependencies.append(d)

    def _set_dependencies(self, tokens):
        """
        sets dependencies

        where t[0] is the use flag if the dependency can be toggled in the ebuild, else None
        and t[1] is the dependency
    
        """        
        dependencies = []
        i = 0
        try:
            while i < len(tokens):
                token = tokens[i]
                if patterns["atom"].match(token):
                    # the token is a non-toggleable dependency
                    _ = get_atom_name(token)["atom"]
                    dep=Dependency(_, self)
                    dependencies.append(dep)
                elif patterns["inclusive_or"].match(token):
                    while token != "(":
                        token = tokens[i]
                        i+=1
                    while token != ")":
                        token = tokens[i]
                        i+=1
                        if patterns["atom"].match(token):
                            _ = get_atom_name(token)["atom"]
                            dep=Dependency(_, self)
                            dependencies.append(dep)
                elif patterns["exclusive_or"].match(token):
                    while token != "(":
                        i += 1
                        token = tokens[i]
                    while token != ")":
                        i += 1
                        token = tokens[i]
                        if patterns["atom"].match(token):
                            _ = get_atom_name(token)["atom"]
                            dep=Dependency(_, self)
                            dependencies.append(dep)
                elif patterns["at_most"].match(tokens[i]):
                    token = tokens[i]
                    while token != "(":
                        i += 1
                        token = tokens[i]
                    while token != ")":
                        i += 1
                        token = tokens[i]
                        if patterns["atom"].match(token):
                            _ = get_atom_name(token)["atom"]
                            dep=Dependency(_, self)
                            dependencies.append(dep)
                elif patterns["flag"].match(token):
                    # a flag can be declared with or without parenthesis
                    # e.g. cups? ( net-lib/wireless ) OR
                    # !cups? !package/my-atom:2
                    # or nested
                    # flag? (
                    #   flag2? (
                    #       >=blah
                    #    )
                    #)
                    flag = UseFlag(token)
                    if tokens[i+1] < len(tokens):
                        i+=1
                        if token == "(":
                            while token != ")":
                                i+1
                                token=tokens[i]
                                if self._is_useflag(token):
                                    subflag=UseFlag(token)
                                    if tokens[i+1] < len(tokens):
                                        i+1
                                        subtoken=tokens[i]
                                        if subtoken == "(":
                                            while subtoken != ")":
                                                i+1
                                                subtoken=tokens[i]
                                                if patterns["atom"].match(subtoken):
                                                    _ = get_atom_name(subtoken)["atom"]
                                                    dep=Dependency(_, self, useflag=subflag)
                                                    dependencies.append(dep)
                                elif patterns["atom"].match(token):
                                    _ = get_atom_name(token)["atom"]
                                    dep=Dependency(_,self,useflag=flag)
                                    dependencies.append(dep)


                i += 1
            for d in dependencies:
                if d.useflag:
                    self._add_useflag(d.useflag)         
                self._add_dependency(d)

        except Exception as e: 
            return (i, tokens, e)
    
        finally:
            return (None, None,  None)
    def _add_useflag(self, useflag):
        if not useflag.name in [x.name for x in self.useflags]:
            self.useflags.append(useflag)
        return useflag

    def _set_useflags(self, tokens):

        useflags = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if self._is_flag(token):
                flag = UseFlag(token)
                useflags.append(flag)
            elif tokens[i] == "(":
                i += 1
                token = tokens[i]
                while token != ")":
                    if self._is_flag(token):
                        flag = UseFlag(token)
                        useflags.append(flag)
                    i += 1
                    token = tokens[i]
            i += 1
        for f in useflags:
            self._add_useflag(f)

    def _get_flag(self, flag_str):
        f = get_flag_name(flag_str)["name"]
        for i,_f in enumerate(self.useflags):
            if _f.name==f:
                flag=self.useflags[i]
                return flag
        return UseFlag(flag_str)
    @staticmethod
    def _is_flag(flag_str):
        if patterns["flag"].match(flag_str):
            return True
            
    def _set_required_use(self, tokens):
        useflags = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if  self._is_flag(token):
                flag = self._get_flag(token)
                useflags.append(flag)
            if token == "(":
                while token != ")":
                    i+=1
                    token=tokens[i]
                    if self._is_flag(token):
                        flag=self._get_flag(token)
                        useflags.append(flag)
            i += 1
        for f in useflags:
            self._add_useflag(f)

class Dependency(Package):
    def __init__(self, name, parent=None, useflag=None, parse_ebuild=False):
        super().__init__(name, parse_ebuild=parse_ebuild)
        self.parent=parent
        self.useflag=useflag

    def add_useflag(self, useflag):
        self.useflag = useflag

    def __str__(self):
        if self.is_toggleable:
            return f"{parent.name} -> self.name, toggle:{self.useflag.flag}"
        else:
            return f"{parent.name} -> self.name (nontoggleable)"
    def is_toggleable(self):
        return True if self.useflag else False

class Task:
    def __init__(self, task, **kwargs):
        self.task = task
        self.kwargs = kwargs

    def run_task(self):
        if self.task == "pm":
            add_package_mask(self.kwargs["package"])
        if self.task == "pum":
            add_package_use_mask(self.kwargs["package"], self.kwargs["useflag"])
        if self.task == "mtf":
            make_temporary_file(self.kwargs["file_"])
        if self.task == "wtf":
            write_temporary_file(self.kwargs["file_"])




def equery_use(package, options=[]):
    option_string = "-o"
    packages = []
    if options:
        option_string += " ".join([o for o in options])
    cmd = f"equery hasuse {package} {option_string}"
    res = run_subprocess(cmd)
    if res:
        for l in res.split("\n"):
            # each return line is formatted as shown below
            # chromeos-base/chrome-icu:chrome-icu:9999:chromiumos
            package, name, version, repo = l.split(":")
            packages.append((package, name, version, repo))
    return packages


def equery_which(package, options=[]):
    option_string = ""
    if options:
        option_string += " ".join([o for o in options])
    cmd = f"equery -C which {package} {option_string}"
    res=None
    try:
        res = run_subprocess(cmd)
    except:
        zprint(f"no ebuild found for {package}",debug=True)
        zprint(f"searching for {package}",debug=True)
        

    if res:
        res = res.replace("\n", "")
    return res

def equery_list(package, options=[]):
    option_string = ""
    if options:
        option_string += " ".join([o for o in options])
    cmd = f"equery list -f {package}"
    res=[]
    try:
        res = run_subprocess(cmd)
    except:
        zprint(f"no ebuilds found for {package}",debug=True)
    if res:
        res = res.replace("\n", "")
        res = [r for r in res.split(" ")]
    return res

def equery_depends(package, options=[]):
    option_string = ""
    if options:
        option_string += " ".join([o for o in options])
    cmd = f"equery depends -a  {package} {option_string}"
    res = None
    try:
        res = run_subprocess(cmd)
    except cros_build_lib.RunCommandError:
        zprint(f"the package:{package} has no dependencies")

    if res:
        deps = set()

        for x in [get_atom_name(x)["atom"] for x in res.split("\n")]:
            if x != "":
                deps.add(x)
        return deps
    return res


def try_remove_package(package):
    """
    tries to remove a package from the build via the following steps
        run ```equery_depends``` to collect all the 'upstream' dependencies
        each dependency is serialized into a `Package``, which contains all use flags and other metadata
        for each upstream dependency:
            check to see if the dependency is controlled by a use flag by running is_toggleable_dependency
            if True:
                create a new task:
                    add_package_use_mask: upstream_dependency, toggleable_use_flagy
            else:
                check to see if there are additional upstream dependencies on the package
                if not:
                    prompt the user: the package:{dependency} depends on {target} and is non toggleable, add this
                    package to the package.mask file?
                    if y:
                        add a new task:
                            add_package_mask: upstream_dependency
                    if n:
                        add to `nonoptional_dependencies`
                if True:
                    warn user: the package: {dependency} depends on target and is non toggleable. The package:
                    {dependency} also has the following reverse dependencies:
                        - list of dependencies

                    continue?
                    if True:
                        add this package to `nonoptional_dependencies` with all of it's reverse dependencies
                        (recursively call)
                    if False:
                        break

        prior to running all tasks, print a summary of what is going to be performed.

        Adding the following to package.use.mask
          - package.name useflag
          -

        Adding the following to package.mask
         - package.name

        Failed to remove the following packages automatically
        Recommend manual removal:
         - package.name
           dependencies
             - package.name
             - ..

    """
    orig_package = package
    nonoptional_dependencies = []
    package_use_masks = []
    package_masks = []
    tasks = []
    messages = {
        "no_toggle": Template(
            "the package:$dependency depends on $target and is non toggleable, add this package to the package.mask file?"
        ),
        "no_toggle_with_deps": Template(
            ": the package: $dependency depends on $target and is non toggleable. The package: $dependency also has additional reverse dependencies that cannot be removed automatically - the user will need to manually remove the package - continue?"
        ),
        "exit": "user cancelled, no changes made",
    }
    dependencies=equery_depends(package)
    for dependency in dependencies:
        d_name=get_atom_name(dependency)["atom"]
        
        d=Dependency(d_name, parse_ebuild=True)
        pprint.pprint(d.metadata)
        pprint.pprint(d.get_use_flags())
        pprint.pprint(d.get_dependencies(return_packages=False))
        # check to see if the original package can be toggled
        useflag = d.useflag
        if useflag and useflag.optional:
            task = Task("pum", package=d.name, useflag=useflag.name)
            tasks.append(task)
            package_use_masks.append((d.name, useflag))
        else:
            # check if upstream dependencies
            subdeps = equery_depends(d.name)
            proceed = False
            if not subdeps:
                proceed = prompt_yn(
                    messages["no_toggle"].substitute(
                        dependency=d.name, target=orig_package
                    )
                )
                if proceed:
                    task = Task("pm", package=d.name)
                    tasks.append(task)
                    package_masks.append(d.name)
                else:
                    print(messages["exit"])
                    sys.exit(1)
            else:
                proceed = prompt_yn(
                    messages["no_toggle_with_deps"].substitute(
                        dependency=d.name, target=orig_package
                    )
                )
                if proceed:
                    nonoptional_dependencies.append(d.name)
                else:
                    print(messages["exit"])
                    sys.exit(1)
    proceed = prompt_yn(
        report.render(
            original_package=orig_package,
            package_use_masks=package_use_masks,
            package_masks=package_masks,
            nonoptional_dependencies=nonoptional_dependencies,
        )
    )
    if proceed:
        run_tasks(tasks)
    else:
        print(messages["exit"])


def run_tasks(task_list):
    # make a local copy to add pre-post tasks
    from collections import deque

    tasks_ = deque()
    ok = prompt_yn(f"run all tasks to complete removal?")
    if ok:
        tasks_.appendleft(
            Task(
                "mtf",
                file_=f"{CHROMEOS_TARGET_PROFILES_ROOT}/package.mask",
            )
        )
        tasks_.appendleft(
            Task(
                "mtf",
                file_=f"{CHROMEOS_TARGET_PROFILES_ROOT}/package.use.mask",
            )
        )

        for t in task_list:
            tasks_.appendleft(t)
        tasks.appendleft(
            Task(
                "wtf",
                file_=f"{CHROMEOS_TARGET_PROFILES_ROOT}/package.mask",
            )
        )
        tasks.appendleft(
            Task(
                "wtf",
                file_=f"{CHROMEOS_TARGET_PROFILES_ROOT}/package.use.mask",
            )
        )

    current = tasks_.pop()
    while current:
        current.run_task()
        current = tasks_.pop()

    else:
        print("user cancelled - no changes made")
        sys.exit(1)


def main(argv: Optional[List[str]]) -> Optional[int]:
    """Main."""
    global DEBUG, OUTPUT
    commandline.RunInsideChroot()
    parser = get_parser()
    opts = parser.parse_args(argv)
    if opts.verbose:
        DEBUG = True
    try_remove_package(opts.package)
