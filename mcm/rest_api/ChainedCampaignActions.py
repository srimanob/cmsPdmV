#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from couchdb_layer.prep_database import database
from json_layer.chained_request import chained_request
from json_layer.chained_campaign import chained_campaign
from json_layer.campaign import campaign
from json_layer.request import request
from RestAPIMethod import RESTResource
from json_layer.action import action

class CreateChainedCampaign(RESTResource):
    def __init__(self):
        self.db = database('chained_campaigns')
        self.adb = database('actions')
        self.ccamp = None
    
    def PUT(self):
                return self.create_campaign(cherrypy.request.body.read().strip())

    def create_campaign(self, jsdata):
        try:
            self.ccamp = chained_campaign(json_input=loads(jsdata))
        except chained_campaign('').IllegalAttributeName as ex:
            return dumps({"results":str(ex)})

        self.logger.log('Creating new chained_campaign %s...' % (self.ccamp.get_attribute('_id'))) 
        
        self.ccamp.set_attribute("_id", self.ccamp.get_attribute("prepid"))
        if not self.ccamp.get_attribute("_id") :#or self.db.document_exists(self.ccamp.get_attribute("_id")):
            self.logger.error('Campaign %s already exists. Cannot re-create it.' % (self.ccamp.get_attribute('_id')))
            return dumps({"results":'Error: Campaign '+self.ccamp.get_attribute("_id")+' already exists'})
        
        # update actions db
        self.update_actions()

	# update history
	self.ccamp.update_history({'action':'created'})
        
        return dumps({"results":self.db.save(self.ccamp.json())})
    
    # update the actions db to include the new chain
    def update_actions(self):
        # get all campaigns in the chained campaign
        camps = self.ccamp.get_attribute('campaigns')
 
        self.logger.log('Updating actions for new chained_campaign %s ...' % (self.ccamp.get_attribute('_id')))
        
        # for every campaign with a defined flow
        for c, f in camps:
            if f:
                # update all its requests
                self.update_action(c)
    
    # find all actions that belong to requests in cid
    # and append cid in the chain
    def update_action(self,  cid):
        rel_ac = self.adb.query('member_of_campaign=='+cid)
        for a in rel_ac:
            # avoid duplicate entries
            if cid not in a['chains']:
                # append new chain id and set to 0
                a['chains'][cid]['flag']=False
                # save to db
                self.adb.update(a)

class UpdateChainedCampaign(RESTResource):
        def __init__(self):
                self.db = database('chained_campaigns')
                self.ccamp = None

        def PUT(self):
                return self.update_campaign(cherrypy.request.body.read().strip())

        def update_campaign(self, jsdata):
                try:
                        self.ccamp = chained_campaign(json_input=loads(jsdata))
                except chained_campaign('').IllegalAttributeName as ex:
                        return dumps({"results":False})

                if not self.ccamp.get_attribute("_id"):
                        self.logger.error('prepid returned was None')
                        return dumps({"results":False})

                self.logger.log('Updating chained_campaign %s ...' % (self.ccamp.get_attribute('_id')))

		# update history
		self.ccamp.update_history({'action':'updated'})

                return dumps({"results":self.db.update(self.ccamp.json())})

        
class AddRequestToChain(RESTResource):
    def __init__(self):
        self.request_db = database('requests')
        self.campaign_db = database('campaigns')
        self.chained_db = database('chained_requests')
        self.ccamp_db = database('chained_campaigns')
        self.campaign = None

    def POST(self, *args):
        if not args:
            return dumps({"results":False})
        if len(args) < 2:
            return dumps({"results":False})
        return self.import_request(args[0], args[1])

    def add_request(self, chainid, campaignid):

        self.logger.log('Generating new request to add in %s...' % (chainid))

        if not chainid:
            self.logger.error('chained_request\'s prepid was None.') 
            return dumps({"results":False}) 
        else:
            try:
                chain = chained_request(chained_request_json=self.chained_db.get(chainid))
            except Exception as ex:
                self.logger.error('Could not initialize chained_request object. Reason: %s' % (ex))
                return dumps({"results":False})
        if not campaignid:
            self.logger.error('id of the campaign provided was None')
            return dumps({"results":False})
        else:
            try:
                camp = campaign(campaign_json=self.campaign_db.get(campaignid))
            except Exception as ex:
                self.logger.error('Could not initialize campaign object. Reason: %s' % (ex))
                return dumps({"results":False})
        req = camp.add_request()
        new_req = chain.add_request(req)
        
        # save everything
        if not self.chained_db.save(chain.json()):
            self.logger.error('Could not save newly created request to database.')
            return dumps({"results":False})
        return dumps({"results":self.request_db.save(new_req)})

class DeleteChainedCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'chained_campaigns'
        self.db = database(self.db_name)
        self.adb = database('actions')
    def DELETE(self, *args):
        if not args:
            return dumps({"results":False})
        return self.delete_request(args[0])
        
    def delete_request(self, id):
        if not self.delete_all_requests(id):
            return dumps({"results":False})
            
        # update all relevant actions
        self.update_actions(id)
        
        return dumps({"results":self.db.delete(id)})
        
    def update_actions(self,  cid):
        # get all actions that contain cid in their chains
        actions = self.adb.query('chain=='+cid)
        for a in actions:
            if cid in a['chains']:
                # delete the option of cid in each relevant action
                del a['chains'][cid]
                self.adb.update(a)

    def delete_all_requests(self, id):
        rdb = database('chained_requests')
        res = rdb.query('member_of_campaign=='+id, page_num=-1)
        try:
            for req in res:
                rdb.delete(req['value']['prepid'])
            return True
        except Exception as ex:
            print str(ex)
            return False

class GetChainedCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'chained_campaigns'
        self.db = database(self.db_name)
    def GET(self, *args):
        if not args:
            self.logger.error('No arguments were given.')
            return dumps({"results":False})
        return self.get_request(args[0])
    def get_request(self, id):
        return dumps({"results":self.db.get(id)})
      

class GenerateChainedRequests(RESTResource):
    def __init__(self):
        self.crdb = database('chained_requests')
        self.ccdb = database('chained_campaigns')
        self.cdb = database('campaigns')
        self.adb = database('actions')
    
    def GET(self,  *args):
        if not args:
            self.logger.error('No arguments were given') 
            return dumps({"results":'Error: No arguments were given'})
        return self.generate_requests(args[0])
    
    def generate_requests(self,  id):
        self.logger.log('Generating all selected chained_requests for chained_campaign %s...' % (id))       
 
        # init chained_campaign
        try:
            cc = chained_campaign(json_input=self.ccdb.get(id))
        except Exception as ex:
            self.logger.error('Could not initialize chained_campaign object. Reason: %s' % (ex))
            return dumps({"results": str(ex)})
        
        # get the campaigns field and from that...
        camps = cc.get_attribute('campaigns')
        # ... the root campaign (assume it is the first, since non-root campaigns are only appended to chains)
        rootc = camps[0][0]
        
        # get all the actions of requests that belong to the root campaign
        rootreqs = self.adb.query('member_of_campaign=='+rootc)
        rreqs = map(lambda x: x['value'],  rootreqs)
        
        # find all actions that have selected this chained campaign
        for ract in rreqs:
            if ract['chains'][id] is not None:
                if ract['chains'][id]['flag']:
                    # check if the chain already exists
                    accs = map(lambda x: x['value'],  self.crdb.query('root_request=='+ract['_id']))
                    flag = False
                    for acc in accs:
                        if id == acc['_id'].split('-')[1]:
                            flag = True
                            break
                
                    if flag:
                        self.logger.error('A chained_request with the id %s already exists' % (id), level='warning')
                        continue
                    
                    # create the chained requests
                    new_req = cc.generate_request(ract['prepid'])
                    # save to database
                    self.crdb.save(new_req)
                    self.ccdb.update(cc.json())
                    
        return dumps({"results":True})

# starts the chained campaign
class Start(RESTResource):
    def __init__(self):
        self.ccdb = database('chained_campaigns')
    
    def GET(self,  *args):
        if not args:
            self.logger.error('No arguments were given') 
            return dumps({"results":'Error: No arguments were given'})
        return self.start(args[0])
    
    def start(self,  ccid):
        if not self.ccdb.document_exists(ccid):
            self.logger.error('chained_campaign %s does not exist' % (ccid))  
            return dumps({"results":'Error: The Chained Campaign does not exist'})

        self.logger.log('Starting chained_campaign %s ...' % (ccid))        

        cc = chained_campaign(self.ccdb.get(ccid))
        cc.start()
        self.ccdb.update(cc.json())

# stops the chained campaign
class Stop(RESTResource):
    def __init__(self):
        self.ccdb = database('chained_campaigns')
    
    def GET(self,  *args):
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})
        return self.stop(args[0])
    
    def stop(self,  ccid):
        if not self.ccdb.document_exists(ccid):
            self.logger.error('chained_campaign %s does not exist.' % (ccid) )
            return dumps({"results":'Error: The Chained Campaign does not exist'})

        self.logger.log('Stopping chained_campaign %s ...' % (ccid))
        
        cc = chained_campaign(self.ccdb.get(ccid))
        cc.stop()
        self.ccdb.update(cc.json())
