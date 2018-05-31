#!/usr/bin/env python3

import sys
import re
import untangle
import json
import dictlib
import tomd
from jira import JIRA

import config

print("Loading File: " + sys.argv[1])
obj = untangle.parse(sys.argv[1])

issues = dict()

maps = dictlib.Obj(config.maps)

class XmlWrapper(object):
    label = 'unknown'
    entry = None
    data = None

    def __init__(self, entry):
        self.entry = entry
        self.data = dictlib.Obj()

    def __repr__(self):
        return self.label

    def error(self, *msg):
        sys.exit("{}: {}".format(self.label, msg[0].format(*msg[1:])))

    def import_xmap(self, key, newkey=None, xmap=None):
        dmap = maps.get(xmap)
        value = dmap.get(getattr(self.entry, key).cdata)
        if not value:
            self.error("Unable to map key={} through {}", key, mapkey)
        if newkey:
            self.data[newkey] = value
        else:
            self.data[key] = value
        return value

    def import_key(self, key, default=None):
        # aggregate if multiples - garr (see fixVersion)
        def getit(entry, key):
            return getattr(entry, key).cdata
        return self._import(key, getit, (self.entry, key), default=default)

    def import_attr(self, kattr, default=None):
        key, attr = kattr.split('.')
        def getit(entry, key, attr):
            return getattr(entry, key)[attr]
        return self._import(kattr, getit, (self.entry, key, attr), default=default)

    def _import(self, store, func, fargs, default=None):
        try:
            value = func(*fargs)
        except:
            if default is None:
                self.error("Unable to find " + store)
            else:
                value = default
        self.data[store] = value
        return value

uniq = set()
data = dict()
issues = dict()

################################################################################
def html2wiki(input):
    output = tomd.convert(input)
    output = re.sub(r'^##*', 'h1.', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'<a name="[^"]+"></a>', '', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'<br/>', '', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'\t+1\.', '1.', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'\t+-', '*', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'^\s*<li>', '*', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'<li>', '\n*', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'</li>', '', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'<ins>', '', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'<ul>', '', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'<(th|td|ul|font|ins|img)[^>]+/?>', '', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'</(th|td|ul|font|ins|img)>', '', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'<h4>', '#', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'</h4>', '', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'&gt;', '>', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'&lt;', '<', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'&amp;', '&', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'^1.', '#', output, flags=re.MULTILINE|re.IGNORECASE)
    output = re.sub(r'\[([^\]]+)\]\(([^\)+])\)', '[\2|\1]', output, flags=re.MULTILINE|re.IGNORECASE)
    return output

################################################################################
for ent in obj.rss.channel.item:

    #####################################################
    # EXPORT (import)
    #####################################################
    impissue = XmlWrapper(ent)
    impissue.label = impissue.import_key('key')
    idata = impissue.data # barf on not encapsulating, but meh
    issues[idata.key] = idata
    impissue.import_xmap('project', xmap='projects')
    impissue.import_key('summary')
    impissue.import_key('title')
    # s/[ID]//
    impissue.import_key('description')
    idata.description = html2wiki(idata.description)
    impissue.import_key('type')
    impissue.import_key('priority')
    impissue.import_key('status')
    impissue.import_key('resolution')
    impissue.import_key('security')
    impissue.import_key('assignee')
    impissue.import_attr('assignee.username')
    impissue.import_key('reporter')
    impissue.import_attr('reporter.username')

    labels = impissue.data['labels'] = list()
    try: 
        for label in ent.labels.label:
            impissue.data['labels'].append(label.cdata)
    except:
        pass
#        print(impissue.label + ": no labels?")

    fixed = impissue.data['fixVersion'] = list()
    try:
        for ver in ent.fixVersion:
            fixed.append(ver.cdata)
    except:
        pass

    impissue.import_key('component', default='')
    impissue.import_key('due')
    impissue.import_attr('timeoriginalestimate.seconds', default='0')
    impissue.import_attr('timeestimate.seconds', default='0')
    impissue.import_attr('timespent.seconds', default='0')

    comments = impissue.data['comments'] = []

    try:
        for comment in ent.comments.comment:
            comments.append(dict(
              comment=comment.cdata,
              author=comment['author'],
              created=comment['created']
            ))
    except:
        pass
        #print(impissue.label + ": no comments?")

    # attachments

    # subtasks
    subtasks = impissue.data['subtasks'] = list()
    try:
        for subtask in ent.subtasks.subtask:
            subtasks.append(subtask.cdata)
    except:
        pass

    # customfields
    try:
        for field in ent.customfields.customfield:
            id = field['id']
            key = field['key']
            name = field.customfieldname.cdata
            result = set()
            for val in field.customfieldvalues.customfieldvalue:
                result.add(val.cdata)
            result = list(result)
            if len(result) > 1:
                impissue.data[name] = ", ".join(result)
            elif result:
                impissue.data[name] = result[0]
            else:
                impissue.data[name] = ''
    except:
        pass

    ###############################
    # TRANSFORM
    ###############################

    idata.project = maps.issue2proj.get(idata.key)
    if not idata.project:
        idata.project = maps.component2proj.get(idata.component)
        if not idata.project:
            print("no map {} component={}".format(impissue, idata.component))
            print("    " + idata.summary)

    newcomponent = maps.components.get(idata.component)
    if newcomponent:
        idata.component = newcomponent

    ###############################
    newtype = maps.types.get(idata.type)
    if idata.type == 'Improvement':
        if idata.comments:
            idata.type = 'Story'
        else:
            idata.type = 'Want'
            if idata.component:
                idata.component = idata.project + ": " + idata.component
            else:
                idata.component = idata.project
            idata.project = 'PLN'
    elif newtype:
        idata.type = newtype
    else:
        sys.exit("no type mapped for: " + newtype)
        
    ###############################
    key = idata.type
    try:
        if not data.get(key):
            data[key] = set([idata.key])
        else:
            data[key].add(idata.key)
    except:
        import traceback
        traceback.print_exc()
        print(json.dumps(idata, indent=2))

    ###############################
    templabels = set(idata.labels)
    templabels.add("TEMP-IMPORT")
    idata.labels = list(templabels)

    ###############################
    newpri = maps.priority.get(idata.priority)
    if newpri != 'Emergency':
        idata.labels = idata.labels.append("Legacy-Priority-" + idata.priority)
    idata.priority = newpri

    ###############################
    newstat = maps.statuses.get(idata.status)
    if not newstat:
        sys.exit("Unable to map status: " + idata.status)
    idata.status = newstat

#sys.exit(0)
################################################################################
print("Connecting to jira: " + config.jira_url)
jira = JIRA(config.jira_url, auth=config.jira_auth)

for key in data:
    for iid in data[key]:
        issue = issues[iid]
        #print("{} {}: {} <<<{}>>>".format(issue.project, key, issue.summary, issue.status))
        print("{} {}: {}".format(issue.project, key, issue.summary, issue.status))

    ################################################################################
    # LOAD
    ################################################################################
    #    'title' appears to be a relic, a dup of summary w/ID prepended

#        jissue = jira.create_issue(
#            project=idata.project,
#            summary=idata.summary,
#            description=idata.description,
#            issuetype={'name': idata.type },
#            labels=idata.labels)
#        print(jissue)
#        if idata.component:
#            issue.update(notify=False, fields={"components": {"name": val for val in idata.component}})
#        if idata.status:
#            issue.update(notify=False, fields={"status": {"name": idata.status}})
#        if idata.labels:
#            issue.update(notify=False, fields={"labels": {"name": val for val in idata.labels}})
#        sys.exit(0)
#    'resolution'
#    'assignee'
#    'assignee.username'
#    'reporter'
#    'reporter.username'
#    'fixVersion'
#    'component'
#    'due'
#    'timeoriginalestimate.seconds'
#    'timeestimate.seconds'
#    'timespent.seconds'
#    comments
#    subtasks
#    customfields
#      customer => custom_field11001
    #)


#print(json.dumps(data, indent=2))
#    print(json.dumps(issue.data, indent=2))
#    sys.exit(0)

#print(uniq)
