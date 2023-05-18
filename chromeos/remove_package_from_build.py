# found in the LICENSE file.
import os
import argparse
import re
import atexit
import signal
import yaml
import datetime
import subprocess
from functools import partial
from typing import List, Optional

from chromite.lib import commandline
from chromite.lib import portage_util
from chromite.lib import cros_build_lib
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
OUTPUT = {"package": "", "modified": [], "failed": []}
"""
# tasks is a list of sequential tasks to perform as a result of the remove_package process
    - add_use_mask
    - 
"""
TASKS = []


def zprint(s: str, debug: bool = False):
    if all([DEBUG, debug]):
        print(s)
    if not debug:
        print(s)


def get_parser() -> commandline.ArgumentParser:
    """Build the argument parser."""
    parser = commandline.ArgumentParser(description=__doc__)
    
    parser.add_argument("-p", "--package", help="Package.", required=True)
    parser.add_argument("--vbose",action="store_true", help="debug logging", default=False)
    parser.add_argument("-o", "--output", type="path", help="output file", required=True)
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
    res = subprocess.run(
        cmd, shell=True, stdout=subprocess.STDOUT, stderr=subprocess.PI{PE
    )
    if res.returncode == 0:
        return res.stdout.decode("utf-8")
    else:
        raise Exception(
            f"a subprocess returned a non-zero exit code: {res.returncode}, error: {res.stdout.decode('utf-8')}"
        )


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
import re
from typing import Sequence, Union

def cr(parts:Sequence=[], 
       group:Union(bool,str)="", 
       is_set:bool=False,
       zom:bool=False,
       oom:bool=False,
       optional:bool=False,
       compile:bool=False)->str:
    """
    convenience for building a `complex` regex string
    each part is a 2-tuple:
      (operation, content)
    where operation is one of
        ''              : append as is
        'g:<name>'      : group as a named group (?P<..>)
        'g'             : group without naming ()
        's'             : wrap the part in a set []
        'e'             : escape each char in the sequence and append
        "*"             : is zero or more
        "+"             : is one or more
        "?"             : is optional

        operator precedence is:
        e s g(named or unnamed) *+?
        
        example, if the operation is:
        'e,s,g,?', and the string is 'foo?', the output will be
        '([foo\?])?'
    
    each 'part' is processed, then added to the output string. It's recommended to
    limit the use of named groups in the inner operations.

    ```cr``` also has top level operations, which apply to the whole
    regular expression, in the same operator precendence as above
    
    Args: 
        parts       : as defined above
        group       : (bool, str) if bool, create an unnamed group, if str, create a
                  named group
        is_set      : if True, wrap the regular expression in a set []
        zom         : if True, append a *
        oom         : if True, append a +
        optional    : if True, append a ?
        compile     : if True, compile the expression before returning

    this function may seem like overkill, but it's useful when reusing 
    multiple expressions within expressions, as the output of `cr` can be used 
    as a part in another higher level regular expression

    if you've ever worked on very long regular expressions, you can most
    likely attest to the amazing amount of frustration caused by
    unmatched parentheses or a misplaced */? breaking the entire sequence.

    example

    patterns = {}

    patterns["example1"] = cr(
        [
            # moderately complex 
            (),
            (),
            ()
        ]
    )

    patterns["example2"] = cr(
        [

            # more complex
            ("?", patterns["example1"])
            (),
            (),
            (),
            ..
        ],
        group="mycomplexregex"
    )
    """
    r_string=""
    option_priority={
        's'        : 100,
        'g'        : 200,
        'e'        : 300,
        'g:.+'     : 400,
        '(\*|\+)'  : 500,
        '\?'       : 600
    }
    def _op(o):
        for k,v in option_priority.items():
            if re.match(k, o):
                return v
    def _group(name="", r_string=""):
        _ = "" 
        if name:
            _=f"(?P<{name}>{r_string})"
        else:
            _+=f"({r_string})"
        return _

    def options_(option_string):
        options=option_string.split(",")
        if len(options)==1 and options[0]=="":
            options=None
            return options
        else:
            return sorted(options, key=_op)
    
    for p in parts:
        # begin processing all parts
        s_string=""
        options=options_(p[0])
        if not options:
            if type(p[1])==str:
                s_string=p[1]
            elif type(p[1])==list:
                s_string="".join([x for x in p[1]])
            r_string+=s_string
            next
        else    :   
            """
            precendence of operations
            e s g, *+?
            """
            # first, compress the string and escape it
            if 'e' in options:
                if type(p[1])==str: 
                    s_string+=re.escape(p[1])
                elif type(p[1])==list:
                    s_string+=re.escape("".join(x for x in p[1]))
                    del options[options.index("e")]
            else:
                if type(p[1])==str: 
                    s_string+=p[1]
                elif type(p[1])==list:
                    s_string+="".join(x for x in p[1])
            for o in options:
                if o=="s":
                    s_string=f"[{s_string}]"
                if o=="g":
                    s_string=_group(name="", r_string=s_string)
                if re.match("g:.+",o):
                    name = o.split(":")[1]
                    s_string=_group(name=name, r_string=s_string)
                if o in ["*", "+"]:
                    s_string=f"{s_string}{o}"
        # end parts - Append the 'part'
            r_string+=s_string
    if is_set:
            r_string=f"[{r_string}]"    
    if group:
        if type(group)==bool:
            r_string=_group("", r_string)
        elif type(group)==str:
            r_string=_group(group, r_string)
    if zom:
        r_string=f"{r_string}*"
    if oom:
        r_string=f"{r_string}+"
    if optional:
        r_string=f"{r_string}?"
    if compile:
        return re.compile(r_string)
    else: 
        return r_string


patterns = {} 


patterns["use"]=cr([
        ("","(REQUIRED_|I)?USE="),
        ("","\""),
        ("es*","-+"),
        ("esg", "A-Za-z0-9-+_"),


    ],
    group="use")

class Package:

    _use_pattern=cr()
    _dependency_pattern=cr()
    def __init__(self, name):
        self.name=name
        self.dependencies=None
        self.useflags=None
        self.filepath=None
    def _parse_ebuild(self):
        """
        parses an ebuild file - adds all dependencies
        to `self.dependencies`

        adds all useflags to `self.useflags`

        rather than use the built in `equery` tool, this reads the content directly and uses
        regex to parse the pattern
        """
        pass

    def _getmetadata(self):
        self.filepath=equery_which(self.name)

    def _get_dependencies(self):
        """
        returns a list of tuples
        
        where t[0] is the use flag if the dependency can be toggled in the ebuild, else None
        and t[1] is the dependency
        """
        pass



    def _get_useflags(self, enabled_only=False):
        """
        if enabled_only, returns only toggled useflags
        """
        pass

        

def equery_use(package, options=[]):
    option_string = "-o -F '$cp:$name:$fullversion:$repo"
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
    res = run_subprocess(cmd)
    return res



def get_dependencies_with_use_flags(dependency_string):
    """
    the output from ```equery_depends``` is a string for each
    dependency formatted as follows:
        net-fs/samba-4.16.8-r2 (cups ? net-print/cups)
        net-print/cups-filters-1.28.17 (>=net-print/cups-1.7.3)
    returns a list of tuples[2] if the dependency is optional (controlled by a USE flag, else False
    """
    dependencies = []
    dep = re.compile("(?P<dep>\([\s\?\>\<=\._\-A-Za-z0-9/\[\]]+\))")
    useflag = re.compile(
        "\((?P<use>[a-zA-Z_\-0-9]+\s\?)?\s?(?P<dep>[a-zA-Z0-9\-\_\<\>=/\.\:\[\]]+)\)"
    )
    for d in dep.finditer(dependency_string):
        full_dependency = d.group("dep")
        use_match = useflag.match(full_dependency)
        if use_match:
            use = use_match.group("use")
            dependency = use_match.group("dep")
            dependencies.append((use, dependency))

    return dependencies


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
            f"not adding the package: {package} to packages.mask,  it already exists",
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
    OUTPUT["masked"] = True


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
            OUTPUT["modified"].append(
                {
                    "package": package,
                    "ebuild_path": ebuild_path,
                    "use_flag": use_flag,
                }
            )
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


def try_remove_package(package):
    """
    tries to remove a package from the build via the following steps
        run ```equery_depends``` to collect all the 'upstream' dependencies
        each dependency is serialized into a ``Dependency``, which contains all use flags and other metadata
        for each upstream dependency:
            check to see if the dependency is controlled by a use flag by running is_optional_dependency
            if is_optional:
                add the use flag and upstream packages to the package_use_mask list
            else:
                prompt the user regarding a non-optional dependency
                    if continue:
                        add the non-optinal dependency to the output file. The user must handle these manually
                    else:
                        break and exit, do not perform any changes
        if ok to continue:
            for each use flag and upstream package:
                add the appropriate string to the package.use.mask file

        add the package to the package.mask file
        print status

    """
    package_use_masks = []
    failed_to_remove = []
    dependencies = equery_depends(package)
    for dependency in dependencies:
        zprint(dependency, debug=True)
        dependency_package = dependency.split(" ")[0]
        deps_with_use_flags = get_dependencies_with_use_flags(dependency)
        for dep_with_flag in deps_with_use_flags:
            use_flag = dep_with_flag[0]
            if use_flag == None:
                # the dependency is non optional - no use flag
                ok = prompt_yn(
                    f"the upstream dependency:{dependency_package} for package: {package} is non optional -- continue?"
                )
                if not ok:
                    zprint("user cancelled - not removing {package}")
                    sys.exit(1)
                else:
                    zprint(
                        f"continuing removing {package} -- added {dependency_package} to output -- remove manually"
                    )
                    failed_to_remove.append(dependency)
            else:
                # the dependency has a use flag - add it to tasks
                TASKS.append(
                    (
                        f"add_package_use_mask: {dependency_package}, {use_flag}",
                        partial(
                            add_package_use_mask,
                            package=dependency_package,
                            use_flag=use_flag,
                        ),
                    )
                )

    TASKS.append(
        (
            "add_package_mask: {package}",
            partial(add_package_mask, package=package),
        )
    )
    return failed_to_remove


def run_tasks():
    global TASKS
    # make a local copy to add pre-post tasks
    tasks_ = []
    ok = prompt_yn(f"run all tasks to complete removal?")
    if ok:
        tasks.append(
            (
                "make_temp_file",
                partial(
                    make_temporary_file,
                    f"{CHROMEOS_TARGET_PROFILES_ROOT}/package.mask",
                ),
            )
        )
        tasks.append(
            (
                "make_temp_file",
                partial(
                    make_temporary_file,
                    f"{CHROMEOS_TARGET_PROFILES_ROOT}/package.use.mask",
                ),
            )
        )
        tasks.extend(TASKS)
        zprint("running all tasks")
        for t in tasks:
            try:
                zprint(f"running task: {t[0]}")
                func = t[1]
                func()
            except:
                zprint(
                    f"an exception occurred while processing all tasks - verify changes to the profiles"
                )
                raise

        zprint("removing temporary files and writing changes to profiles")
        write_temporary_file(f"{CHROMEOS_TARGET_PROFILES_ROOT}/package.mask")
        write_temporary_file(
            f"{CHROMEOS_TARGET_PROFILES_ROOT}/package.use.mask"
        )
        zprint("completed")
    else:
        zprint("user cancelled - no changes made")


def main(argv: Optional[List[str]]) -> Optional[int]:
    """Main."""
    global DEBUG, OUTPUT
    commandline.RunInsideChroot()
    parser = get_parser()
    opts = parser.parse_args(argv)
    if opts.verbose:
        DEBUG=True
    output_file = opts.output
    failed_packages = try_remove_package(opts.package)
    run_tasks()
    if failed_packages:
        for f in failed_packages:
            OUTPUT["failed"].append(
                {"package": f, "ebuild_path": equery_which(f)}
            )

    # write output
    now = datetime.datetime.now()
    formatted_date = now.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.abspath(output_file), "w") as out_fh:
        out_fh.write(f"# removal log for {opts.package}")
        out_fh.write(f"# generated on {formatted_date}")
        out_fh.write(yaml.dumps(OUTPUT))
