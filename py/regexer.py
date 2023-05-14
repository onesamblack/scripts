## this function helps compose complex regex strings

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


