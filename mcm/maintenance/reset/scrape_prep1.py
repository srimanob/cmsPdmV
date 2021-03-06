#!/usr/bin/env python

# import MySQL connector for python
import MySQLdb

# json lib is only used for visualization of data
import json

# MySQL db and cursor for queries init (cursor is set to json)
db = MySQLdb.connect(host="devdb",user="prepdb", passwd="Testprepdb", db="MonteCarlo")
cursor = db.cursor(cursorclass=MySQLdb.cursors.DictCursor)

# returns the campaign primary key corresponding to the given campaign name
def get_campaign_key(campaign_name):
    q = 'select name, PrKeyPF from Campaign;'
    cursor.execute(q)
    camp_codes = cursor.fetchall()

    for ccode in camp_codes:
        if campaign_name == ccode['name']:
            return ccode['PrKeyPF']
    return -1

# return the requests belonging to the given campaign
def get_requests(campaign_name, limit=-1, constraints = ''):

    results = []

    # find campaign key
    ckey = get_campaign_key(campaign_name)
    if ckey == -1:
        print 'Error: Campaign ' + str(campaign_name) + ' does not exist'
        return []
    # limit 10 => returns only the first 10 requests
    q1 = 'select PrKeyPF from Request where campaignKey = '+str(ckey)
    if constraints:
        q1 += ' and ' + constraints
    if limit > 0:
        q1 += ' limit '+str(limit)
    q1 += ';'


    # execute query
    cursor.execute(q1)

    # get all rows returned
    allrequests = cursor.fetchall()

    # iterate through all requests
    for req in allrequests:

        # find primary key
        prk = req["PrKeyPF"]

        # build query that returns all information about a request in a single json (2 joins: Resources, Options)
        q2 = 'select * from RequestResourcesRel left join Request on RequestResourcesRel.onRequest = Request.PrKeyPF left join Resources on RequestResourcesRel.resources = Resources.PrKeyPF left join RequestOptions on RequestResourcesRel.onRequest = RequestOptions.forRequest where Request.PrKeyPF='+str(prk)+';'

        # execute query
        cursor.execute(q2)

        # append campaign name in the json
        rows = cursor.fetchone()
        rows['member_of_campaign'] = campaign_name

        # collect results
        results.append(rows)

    return results

#convert comma separated strings in prep1 in lists for prep2
def splitPrep1String(thestring):
    stringsplit = thestring.split(',')
    li=[]
    for step in stringsplit:
      item = step.split(' ', 1)[0]
      li.append(item)
    return li

# convert the json returned by the cursor to a request object in prep2 db
def morph_requests(request_list):
    return map(lambda x: re_morph(x), request_list)

# aux: converts the date format to the prep2 date format
def convert_date(date,  time=''):
    if '-' in date:
        return date
    toks = date.rsplit('/')
    new_date = ''
    for tok in reversed(toks):
        new_date += tok + '-'
    toks = new_date.rsplit('-')
    if not time:
        for i in xrange(6-len(toks)):
            new_date += '0-'
    else:
        toks = time.rsplit(':')
        for i in reversed(range(len(toks)-1)):
            new_date += toks[i] + '-'
    return new_date.rstrip('-')

# aux: internal conversion of json of mysql to prep2 json
def re_morph(req_json):
    new = {}
    new['_id'] = req_json['code']
    new['prepid'] = req_json['code']
    new['priority'] = req_json['priority']
    new['status'] = req_json['status']
    new['completion_date'] = ''
    new['cmssw_release'] = req_json['swrelease']
    new['input_filename'] = req_json['inputFileName']
    new['pwg'] = req_json['pwg']
    new['validation'] = req_json['validation']
    new['dataset_name'] = req_json['dataSetName']
    new['pileup_dataset_name'] = req_json['pileupDataSetName']
    new['www'] = req_json['www']
    new['process_string'] = req_json['processStr']
    new['input_block'] = req_json['inputBlock']
    new['cvs_tag'] = req_json['cvsTag']
    new['pvt_flag'] = req_json['PVTflag']
    new['pvt_comment'] = req_json['PVTcomment']
    new['mcdb_id'] = req_json['MCDBid']
    new['notes'] = req_json['notes']
    new['description'] = req_json['description']
    new['remarks'] = req_json['remarks']
    new['completed_events'] = -1
    new['total_events'] = req_json['nbEvents']
    new['member_of_chain'] = []
    new['member_of_campaign'] = req_json['member_of_campaign']
    new['time_event'] = req_json['timeEvent']
    new['size_event'] = req_json['sizeEvent']
    new['nameorfragment'] = req_json['genFragment']
    new['version'] = 0
    new['type'] = req_json['type']
    new['generators'] = req_json['generators']
    new['block_black_list'] = []
    new['block_white_list'] = []

    new['submission_details'] = { 'author_name': req_json['authorName'], 'author_cmsid' : req_json['authorCMSid'], 'author_inst_code': req_json['authorInstCode'], 'submission_date': convert_date(req_json['requestDate'].split(' ')[0], req_json['requestDate'].split(' ')[1]), 'author_project': ''}

    new['comments'] = []

    customize1 = splitPrep1String(req_json['customizeName1'])
    customizeF1 = splitPrep1String(req_json['customizeFunction1'])
    cust1 = []
    for index in range(len(customize1)):
      cust1.append(customize1[index].split('.py')[0]+'.'+customizeF1[index])

    customize2 = splitPrep1String(req_json['customizeName2'])
    customizeF2 = splitPrep1String(req_json['customizeFunction2'])
    cust2 = []
    for index in range(len(customize2)):
      cust2.append(customize2[index].split('.py')[0]+'.'+customizeF2[index])

    # split sequences
    se1 = {}
    tok1 = req_json['sequence1'].split('--')
    for tok in tok1:
        if ',' in tok:
            se1['step'] = splitPrep1String(tok.strip())
        else:
            atts = tok.split(' ')
            if len(atts) > 1:
                se1[atts[0].strip('--')] = atts[1]
            else:
                se1[atts[0].strip('--')] = ""

    se2 = {}
    tok2 = req_json['sequence1'].split(' ')
    for tok in tok2:
        if ',' in tok:
            se2['step'] = splitPrep1String(tok)
        else:
            atts = tok.split(' ')
            if len(atts) > 1:
                se2[atts[0].strip('--')] = atts[1]
            else:
                se2[atts[0].strip('--')] = ""


    new['sequences'] = [{'index':0, "slhc": "", "pileupScenario": req_json['pileupScenario'], "beamspot": "Realistic8TeVCollision", "magField": "", "step": splitPrep1String(req_json['sequence1']), "datatier": ['GEN-SIM'], "scenario": "", "geometry": "", "customise": "", "datamix": "", "eventcontent": ['RAWSIM'], "conditions": req_json['conditions']}]

    if req_json['sequence2']:
        new['sequences'].append({'index':1, "slhc": "", "pileupScenario": req_json['pileupScenario'], "beamspot": "Realistic8TeVCollision", "magField": "", "step": splitPrep1String(req_json['sequence2']), "datatier": splitPrep1String(req_json['dataTier']), "scenario": "", "geometry": "", "customise": cust2, "datamix": "", "eventcontent": splitPrep1String(req_json['eventContent']), "conditions": req_json['conditions']})
    for i in range(len(new['sequences'])):
        for att in new['sequences'][i]:
            if i == 1:
                if att in se1:
                    print att, ':', se1[att]
                    new['sequences'][i][att] = se1[att]
            elif i == 2:
                if att in se2:
                    new['sequences'][i][att] = se2[att]


    #[{'index':0, 'step': req_json['step'], 'beamspot':'', 'geometry':'', 'magnetic_field':'', 'conditions':[req_json['conditions']], 'pileup_scenario':[req_json['pileupScenario']], 'datamixer_scenario':[req_json['dataMixerScenario']], 'scenario':'', 'customize_name':req_json['customizeName1'], 'customize_function':req_json['customizeFunction1'], 'slhc':'', 'event_content':[req_json['eventContent']], 'data_tier':[req_json['dataTier']], 'sequence':[req_json['sequence1']]}, {'index':1, 'step': req_json['step'], 'beamspot':'', 'geometry':'', 'magnetic_field':'', 'conditions':[req_json['conditions']], 'pileup_scenario':[req_json['pileupScenario']], 'datamixer_scenario':[req_json['dataMixerScenario']], 'scenario':'', 'customize_name':req_json['customizeName2'], 'customize_function':req_json['customizeFunction2'], 'slhc':'', 'event_content':[req_json['eventContent']], 'data_tier':[req_json['dataTier']], 'sequence':[req_json['sequence2']]} ]

    new['generator_parameters'] = [{'version':0, 'submission_details':{'author_name':'automatic'}, 'cross_section':req_json['crossSection'], 'filter_efficiency': req_json['filterEff'], 'filter_efficiency_error': req_json['filterEffError'], 'match_efficiency': req_json['matchEff'], 'match_efficiency_error': -1}]

    new['reqmgr_name'] = []

    new['approvals'] = build_approvals(req_json['approvals']) # a list
    new['update_details'] = []

    return new

def build_approvals(appstr):

    res = []

    if ':' in appstr:
        toks = appstr.split(':')
        for i in range(len(toks)):
            appstep = toks[i]
            if 'GEN' in toks[i]:
                appstep = 'gen'
            elif 'Defined' in toks[i]:
                appstep = 'defined'
            elif 'SUBMIT' in toks[i]:
                appstep = 'inject'
            elif 'Done' in toks[i]:
                appstep = 'approved'

            app = {'index':i, 'approval_step': appstep, 'approver':{}}
            res.append(app)
    else:
        appstep = appstr
        if 'GEN' in appstr:
            appstep = 'gen'
        elif 'Defined' in appstr:
            appstep = 'defined'
        elif 'SUBMIT' in appstr:
            appstep = 'inject'
        elif 'Done' in appstr:
            appstep = 'approved'

        res.append({'index':0, 'approval_step':appstep, 'approver':{}})

    return res

# retrieve a campaign
def get_campaign(campaign_name):

    # results holder
    results = []

    # find campaign key
    ckey = get_campaign_key(campaign_name)
    if ckey == -1:
        print 'Error: Campaign ' + str(campaign_name) + ' does not exist'
        return []

    # build query to get the campaign details
    q1 = 'select * from Campaign where PrKeyPF = '+str(ckey)+';'

    # execute the query
    cursor.execute(q1)

    # get all rows returned
    camp = cursor.fetchone()

    return camp

def morph_campaign(camp):
    new = {}

    if not camp:
        return new

    new['_id'] = camp['name']
    new['prepid'] = camp['name']
    new['start_date'] = convert_date(camp['startDate'])
    new['end_date'] = convert_date(camp['endDate'])
    new['energy'] = camp['energy']
    new['type'] = [camp['type']]
    new['next'] = []
    new['production_type'] = camp['prodType']
    new['cmssw_release'] = [camp['swrelease']]
    new['description'] = camp['description']
    new['remarks'] = camp['remarks']
    new['status'] = camp['status']
    new['validation'] = camp['validation']
    new['pileup_dataset_name'] = camp['pileupDataSetName'].split(';')
    new['process_string'] = camp['processStr'].split(';')
    new['generators'] = camp['generators'].split(';')
    new['input_filename'] = camp['inputFileName']
    new['www'] = camp['www']
    new['completed_events'] = -1
    new['total_events'] = camp['nbEvt']
    if 'LHE' in new['_id']:
        new['root'] = 0 # root
    elif 'DR' in new['_id']:
        new['root'] = 1 # non root
    else:
        new['root'] = -1 # possible root

    #sequences fix
    customize1 = splitPrep1String(camp['customizeName1'])
    customizeF1 = splitPrep1String(camp['customizeFunction1'])
    cust1 = []
    for index in range(len(customize1)):
      cust1.append(customize1[index].split('.py')[0]+'.'+customizeF1[index])

    customize2 = splitPrep1String(camp['customizeName2'])
    customizeF2 = splitPrep1String(camp['customizeFunction2'])
    cust2 = []
    for index in range(len(customize2)):
      cust2.append(customize2[index].split('.py')[0]+'.'+customizeF2[index])

    # split sequences
    se1 = {}
    tok1 = camp['sequence1'].split(' ')
    for tok in tok1:
        if ',' in tok:
            se1['step'] = splitPrep1String(tok)
        else:
            atts = tok.split(' ')
            if len(atts) > 1:
                se1[atts[0].strip('--')] = atts[1]
            else:
                se1[atts[0].strip('--')] = ""

    se2 = {}
    tok2 = camp['sequence2'].split(' ')
    for tok in tok2:
        if ',' in tok:
            se2['step'] = splitPrep1String(tok)
        else:
            atts = tok.split(' ')
            if len(atts) > 1:
                se2[atts[0].strip('--')] = atts[1]
            else:
                se2[atts[0].strip('--')] = ""


    new['sequences'] = {1: {"default":{'index':0, "slhc": "", "pileupScenario": camp['pileupScenario'], "beamspot": "Realistic8TeVCollision", "magField": "", "step": splitPrep1String(camp['sequence1']), "datatier": splitPrep1String(camp['dataTier'].strip('|')), "scenario": "", "geometry": "", "customise": '', "datamix": "", "eventcontent": splitPrep1String(camp['eventContent']), "conditions": camp['conditions']}}}#,

    if camp['sequence2']:
        new['sequences'][2] = {"default":{'index':1, "slhc": "", "pileupScenario": camp['pileupScenario'], "beamspot": "Realistic8TeVCollision", "magField": "", "step": splitPrep1String(camp['sequence2']), "datatier": splitPrep1String(camp['dataTier'].strip('|')), "scenario": "", "geometry": "", "customise": '', "datamix": "", "eventcontent": splitPrep1String(camp['eventContent']), "conditions": camp['conditions']}}

    for i in range(len(new['sequences'])):
        for att in new['sequences'][i+1]["default"]:
            if i == 0:
                if att in se1:
                    new['sequences'][i+1][att] = se1[att]
            elif i == 1:
                if att in se2:
                    new['sequences'][i+1][att] = se2[att]


    #new['sequences'] = [{'index':0, 'step': -1, 'beamspot':'', 'geometry':'', 'magnetic_field':'', 'conditions':[camp['conditions']], 'pileup_scenario':[camp['pileupScenario']], 'datamixer_scenario':[camp['dataMixerScenario']], 'scenario':'', 'customize_name':camp['customizeName1'], 'customize_function':camp['customizeFunction1'], 'slhc':'', 'event_content':[camp['eventContent']], 'data_tier':[camp['dataTier']], 'sequence':[camp['sequence1']]}, {'index':1, 'step': -1, 'beamspot':'', 'geometry':'', 'magnetic_field':'', 'conditions':[camp['conditions']], 'pileup_scenario':[camp['pileupScenario']], 'datamixer_scenario':[camp['dataMixerScenario']], 'scenario':'', 'customize_name':camp['customizeName2'], 'customize_function':camp['customizeFunction2'], 'slhc':'', 'event_content':[camp['eventContent']], 'data_tier':[camp['dataTier']], 'sequence':[camp['sequence2']]} ]

    new['submission_details'] = { 'author_name': camp['authorName'], 'author_cmsid' : camp['authorCMSid'], 'author_inst_code': camp['authorInstCode'], 'submission_date': convert_date(camp['campaignDate']), 'author_project': ''}
    new['approvals'] = [{'index':0, 'approval_step':'start', 'approver':{}}] if 'Start' in camp['approvals'] else [{'index':0, 'approval_step':'start', 'approver':{}},{'index':1, 'approval_step':'stop', 'approver':{}}]
    new['comments'] = []

    return new

# create actions from all the requests
def create_actions(directory='data/'):
    try:
        import os
    except ImportError:
        print 'Error: Could not import module "os"'
        return False

    # get main dir root
    datadir = os.path.abspath(directory) + '/'
    flist = os.listdir(datadir+'requests/')
    for filename in flist:
         try:
             f = open(datadir + 'actions/' + filename, 'w')
             f.write('{"_id":"'+filename+'", "prepid":"'+filename+'", "member_of_campaign": "'+filename.split('-')[1]+'", "chains":{},"submission_details":{"author_name":"automatic", "author_cmsid":"", "author_inst_code":"", "author_project":"", "submission_date":""}}')
             f.close()
         except Exception:
            print filename + ' could not be an action'


    return True

def create_chained_campaigns(directory='data/'):
	try:
		import os
	except ImportError:
		print 'Error: Could not import module "os".'
		return False

	datadir = os.path.abspath(directory) + '/'

	flist = os.listdir(datadir+'campaigns/')
	for filename in flist:
	    try:
    		fout = open(datadir + 'chained_campaigns/chain_' + filename, 'w')
    		fin = open(datadir + 'campaigns/'+filename, 'r')
	    	camp = json.loads(fin.read())
	    	fin.close()

	    	ccamp = {}
	    	ccamp['prepid'] = camp['prepid']
	    	ccamp['_id'] = camp['prepid']
	    	ccamp['energy'] = camp['energy']
	    	ccamp['campaigns'] = [camp['prepid']]
	    	ccamp['alias'] = camp['prepid']
	    	ccamp['approvals'] = []
	    	ccamp['description'] = 'Dedicated chained campaign for '+camp['prepid']
	    	ccamp['action_parameters'] = {}
	    	ccamp['www'] = 'http://preptest.cern.ch/edit/chained_campaigns/chain_'+camp['prepid']+'/'
	    	ccamp['submission_details'] = {"author_name":"automatic", "author_cmsid":"", "author_inst_code":"", "author_project":"", "submission_date":""}
    		ccamp['comments'] = []
	    	ccamp['valid'] = True

	    	fout.write(json.dumps(ccamp))
	    	fout.close()
	    except Exception as ex:
	        print filename + ' could be a chained_campaign.' +str(ex)

	return True


# auto magic wrapper to get a campaign
def retrieve_campaign(campaign_name):
    return morph_campaign(get_campaign(campaign_name))

# auto magic wrapper for get_requests
def retrieve_requests(campaign_name, limit=-1, constraints=''):
    return morph_requests(get_requests(campaign_name, limit, constraints))

def get_request(prepid=None):
    if not prepid:
        return False
    if '-' not in prepid:
        return False

    camp = prepid.split('-')[1]
    return retrieve_requests(camp, constraints='code like "%'+prepid+'%"')

if __name__=='__main__':

    import os, sys, argparse

    datadir = '/home/prep2/data/'

    parser = argparse.ArgumentParser(description='Export data objects from PREP1 to PREP2 json format.')

    parser.add_argument('-a', '--create-action',
                help='Creates the corresponding action for the new request',
                action='store_true', default=False)
    parser.add_argument('-c', '--create-campaign',
                help='Creates the json for the campaign the request belongs to',
                action='store_true', default=False)
    parser.add_argument('-p', '--prepid',
                help='The list of PREP IDs to export', required=True,
                metavar="PREPID", nargs="+")
    parser.add_argument('-d', '--directory',
                help='The directory to create the new objects',
                metavar='DIRECTORY', default=None)

    args = parser.parse_args()

    if args.directory:
        datadir = os.path.abspath(args.directory)+'/data/'

    # build directory structure
    if not os.path.exists(datadir):
        os.makedirs(datadir + 'requests')

    if args.create_action:
        os.makedirs(datadir + 'actions')
    if args.create_campaign:
        os.makedirs(datadir + 'campaigns')
        os.makedirs(datadir + 'chained_campaigns')

    prepid_list = args.prepid

    for pid in prepid_list:
        req = get_request(pid)

        if not req:
            print 'Error: Could not retrieve results.'
            sys.exit(1)

        try:
            f = open(datadir + 'requests/' + pid, 'w')
            f.write(json.dumps(req[0]))
            f.close()
        except IOError as ex:
            print 'Error: Could not save results to disk. Reason: '+str(ex)
            sys.exit(1)

        if args.create_action:
            create_actions(datadir)

        if args.create_campaign:
            c = retrieve_campaign(pid.split('-')[1])
            try:
                f = open(datadir + 'campaigns/' + pid.split('-')[1], 'w')
                f.write(json.dumps(c))
                f.close()
            except IOError as ex:
                print 'Error: Could not save Campaign object to disk. Reason: '+str(ex)
                sys.exit(1)

            if c['root'] == -1 or c['root'] == 0:
                    create_chained_campaigns(datadir)
