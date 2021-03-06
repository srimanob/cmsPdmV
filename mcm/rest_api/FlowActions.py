#!/usr/bin/env python

import cherrypy
from json import loads, dumps
from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResource
from json_layer.campaign import campaign
from json_layer.flow import flow
from json_layer.action import action
from tools.user_management import access_rights
import traceback


class FlowRESTResource(RESTResource):
    def __init__(self):
        self.db_name = 'flows'
        self.access_limit = access_rights.production_manager

    # takes  a 2 lists and returns a tuple of what is present in the second and not in the first and
    # what was present in the first and not in the second
    # ( in_new_not_old, in_old_not_new)
    def __compare_list(self, old, new):
        # compute diff of two lists ( a - b )
        def diff(a, b):
            b = set(b)
            return [aa for aa in a if aa not in b]

        # init 
        to_be_removed, to_be_created = [], []

        # compute old - new
        to_be_removed = diff(old, new)

        # compute new - old
        to_be_created = diff(new, old)

        # return the tuple
        return to_be_created, to_be_removed

    def update_actions(self, c):
        self.logger.log('Updating actions...')
        adb = database('actions')

        # find all actions that belong to a campaign
        allacs = adb.queries(['member_of_campaign==%s' % c])

        # for each action
        for ac in allacs:
            # init action object
            a = action(json_input=ac)
            # calculate the available chains
            a.find_chains()
            # save to db
            adb.update(a.json())

    def set_default_request_parameters(self, nc, cdb, f):
        # add a skeleton of the sequences of the next (landing) campaign
        # in the new flow (allows for dynamic changing of sequences upon flowing)
        rp = f.get_attribute('request_parameters')
        if nc:
            camp = cdb.get(nc)
            ## that erase all previous values in the flows requests parameters ...
            if not 'sequences' in rp or len(rp['sequences']) != len(camp['sequences']):
                rp['sequences'] = []
                for seq in camp['sequences']:
                    rp['sequences'].append({})
                f.set_attribute('request_parameters', rp)


    def __compare_json(self, old, new):
        return self.update_derived_objects(old, new)

    def update_derived_objects(self, old, new):

        cdb = database('campaigns')
        next_c = new['next_campaign']
        allowed = new['allowed_campaigns']

        # get the changes
        tbc, tbr = self.__compare_list(old['allowed_campaigns'], new['allowed_campaigns'])

        # check to see if you need to update a campaign (if next_c is altered, or a new allowed campaign)
        if old['next_campaign'] != new['next_campaign'] or tbc:
            try:
                self.update_campaigns(next_c, allowed, cdb)
            except Exception as ex:
                self.logger.error('Could not update campaigns. Reason: %s' % ex)
                return {"results": 'Error: update_campaigns returned:' + str(ex)}

        # create new chained campaigns
        try:
            #self.update_chained_campaigns(next_c,  tbc)
            self.update_chained_campaigns(next_c, allowed) #JR. to make sure everything gets propagated
        except Exception as ex:
            self.logger.error('Could not build derived chained_campaigns. Reason: %s' % ex)
            self.logger.error(traceback.format_exc())
            return {"results": 'Error while creating derived chained_campaigns: ' + str(ex)}

        # TODO: delete all chained_campaigns that contain the to_be_removed (tbr) campaigns and 
        #               use this flow.

        # if reached, then successful
        return {'results': True}

    def update_campaigns(self, next_c, allowed, cdb):
        # check to see if next_c is legal
        if not cdb.document_exists(next_c):
            raise ValueError('Campaign ' + str(next_c) + ' does not exist.')

        if not next_c:
            return

        n = cdb.get(next_c)
        if n['root'] == 0:
            raise ValueError('Campaign ' + str(next_c) + ' is a root campaign.')

        # iterate through all allowed campaigns and update the next_c field
        for c in allowed:
            camp = campaign(json_input=cdb.get(c))
            try:
                # append campaign
                camp.add_next(next_c)
            except campaign.CampaignExistsException:
                pass

            # save to database
            cdb.update(camp.json())

    def is_energy_consistent(self, next_c, allowed_c, cdb):
        """
        Checks if the energy of campaigns is consistent (it cannot differ)
        """
        next_energy = next_c.get_attribute('energy')
        for camp in allowed_c:
            mcm_c = campaign(cdb.get(camp))
            if mcm_c.get_attribute('energy') != next_energy:
                return False
        return True

    def are_campaigns_correct(self, next_c, allowed_c, cdb):
        if next_c:
            if not cdb.document_exists(next_c):
                return {"results": False, "message": '{0} is not a valid campaign for next'.format(next_c)}
            next_mcm_c = campaign(cdb.get(next_c))
            if not self.is_energy_consistent(next_mcm_c, allowed_c, cdb):
                return {"results": False,
                        "message": 'Next campaign {0} and allowed campaigns have inconsistent energies'.format(next_c)}
            ##consistency check
            if next_c in allowed_c:
                return {"results": False, "message": "Cannot have next campaign in the allowed campaign"}
        return True

    # create all possible chained campaigns going from allowed.member to next
    def update_chained_campaigns(self, next_c, allowed):
        #### we can switch this method off in order to not generate godzillions of chained campaigns
        ## we have the SelectChainedCampaigns ability for that
        return

        # # check to see if next is legal
        # if not self.cdb.document_exists(next):
        #     raise ValueError('Campaign ' + str(next) + ' does not exist.')
        #
        # n = self.cdb.get(next)
        # self.logger.log('investigating for next ' + next)
        # if n['root'] == 0:
        #     self.logger.error('Campaign %s is a root campaign.' % (next))
        #     raise ValueError('Campaign ' + str(next) + ' is a root campaign.')
        #
        # for c in allowed:
        #     #self.logger.log('investigating for '+c)
        #     # check to see if this chained campaign is already created
        #     fid = self.f.get_attribute('_id')
        #     ##JR. could not find the reason for the next lines
        #     #if fid:
        #     #    if self.ccdb.document_exists('chain_'+c+'_'+fid):
        #     #        continue
        #     #else:
        #     #    if self.ccdb.document_exists('chain_'+c):
        #     #        continue
        #
        #     # init campaign objects
        #     camp = self.cdb.get(c)
        #     #if c is NOT a root campaign
        #     if camp['root'] == 1 or camp['root'] == -1:
        #         # get all chained campaigns that have the allowed c as the last step
        #         ccs = self.ccdb.queries(['last_campaign==%s' % (c)])
        #         self.logger.log('for alst campaign %s' % ( c ))
        #         self.logger.log('found %d to deal with' % (len(ccs)))
        #         self.logger.log('found %s' % ( map(lambda doc: doc['prepid'], ccs) ))
        #         # for each chained campaign
        #         for cc in ccs:
        #             ## skipping the chained campaign that has only the last campaign in it ... WHY ?
        #             #if cc['_id'] == 'chain_'+camp['_id']:
        #             #    continue
        #
        #             nextName = cc['_id'] + '_' + self.f.get_attribute('prepid')
        #
        #             if self.ccdb.document_exists(nextName):
        #                 continue
        #
        #             self.logger.log('treating ' + cc['_id'])
        #
        #             # init a ccamp object based on the old
        #             ccamp = chained_campaign(json_input=cc)
        #
        #             # disable it
        #             ccamp.stop()
        #             # update to db
        #             self.ccdb.update(ccamp.json())
        #
        #             # append the next campaign in the chain
        #             ccamp.add_campaign(next, self.f.get_attribute('prepid'))
        #             # update the id
        #             ccamp.set_attribute('_id', nextName)#ccamp.get_attribute('_id')+'_'+self.f.get_attribute('prepid'))
        #             ccamp.set_attribute('prepid', ccamp.get_attribute('_id'))
        #
        #             # reset the alias
        #             ccamp.set_attribute('alias', '')
        #
        #             # restart chained campaign
        #             ccamp.start()
        #
        #             # save new chained campaign to database
        #             self.ccdb.save(ccamp.json())
        #
        #     # else if c is root campaign:
        #     #if camp['root']==0 or camp['root']==-1:
        #     if camp['root'] == 0:
        #         ccamp = chained_campaign()
        #         # add allowed root
        #         ccamp.add_campaign(c) # assume root. flow=None
        #
        #         # add next with given flow
        #         ccamp.add_campaign(next, self.f.get_attribute('prepid'))
        #
        #         # init campaign objects
        #         camp = campaign(self.cdb.get(c))
        #         # add meta (energy)
        #         ### not there anymore ccamp.set_attribute('energy', camp['energy'])
        #
        #         # add a prepid
        #         if fid:
        #             ccamp.set_attribute('prepid',
        #                                 'chain_' + camp.get_attribute('prepid') + '_' + self.f.get_attribute('_id'))
        #         else:
        #             ccamp.set_attribute('prepid', 'chain_' + camp.get_attribute('prepid'))
        #
        #         ccamp.set_attribute('_id', ccamp.get_attribute('prepid'))
        #
        #         self.ccdb.save(ccamp.json())
        #
        #     # update actions
        #     self.update_actions(c)


class CreateFlow(FlowRESTResource):
    def __init__(self):
        FlowRESTResource.__init__(self)

    def PUT(self, *args, **kwargs):
        """
        Create a flow from the provided json content
        """
        return dumps(self.create_flow(cherrypy.request.body.read().strip()))

    def create_flow(self, jsdata):
        cdb = database('campaigns')
        db = database(self.db_name)
        data = loads(jsdata)
        if '_rev' in data:
            return {"results": 'Cannot create a flow with _rev'}
        try:
            f = flow(json_input=data)
        except flow.IllegalAttributeName as ex:
            return {"results": str(ex)}
        except ValueError as ex:
            self.logger.error('Could not initialize flow object. Reason: %s' % ex)
            return {"results": str(ex)}

        if not f.get_attribute('prepid'):
            self.logger.error('prepid is not defined.')
            return {"results": 'Error: PrepId was not defined.'}

        f.set_attribute('_id', f.get_attribute('prepid'))

        #uniquing the allowed campaigns if passed duplicates by mistake
        if len(list(set(f.get_attribute('allowed_campaigns')))) != f.get_attribute('allowed_campaigns'):
            f.set_attribute('allowed_campaigns', list(set(f.get_attribute('allowed_campaigns'))))

        self.logger.log('Creating new flow %s ...' % (f.get_attribute('_id')))

        nc = f.get_attribute('next_campaign')

        result = self.are_campaigns_correct(nc, f.get_attribute('allowed_campaigns'), cdb)
        if result is not True:
            return result

        ## adjust the requests parameters based on what was provided as next campaign
        self.set_default_request_parameters(nc, cdb, f)

        # update history
        f.update_history({'action': 'created'})

        # save the flow to db
        if not db.save(f.json()):
            self.logger.error('Could not save newly created flow %s to database.' % (f.get_attribute('_id')))
            return {"results": False}

        #return right away instead of trying and failing on missing next or allowed
        if not nc or not len(f.get_attribute('allowed_campaigns')):
            return {"results": True}

        # update all relevant campaigns with the "Next" parameter
        try:
            self.update_campaigns(f.get_attribute('next_campaign'), f.get_attribute('allowed_campaigns'), cdb)
        except Exception as ex:
            self.logger.error('Error: update_campaigns returned:' + str(ex))
            return {"results": 'Error: update_campaigns returned:' + str(ex)}

        # create all possible chained_campaigns from the next and allowed campaigns
        try:
            self.update_chained_campaigns(f.get_attribute('next_campaign'),
                                          f.get_attribute('allowed_campaigns'))
        except Exception as ex:
            self.logger.error(
                'Could not build derived chained_campaigns for flow {0}. Reason: {1}'.format(
                    f.get_attribute('_id'), ex))
            return {"results": 'Error while creating derived chained_campaigns: ' + str(ex)}

        # save to database
        return {"results": True}


class UpdateFlow(FlowRESTResource):
    def __init__(self):
        FlowRESTResource.__init__(self)

    def PUT(self):
        """
        Update a flow with the provided content
        """
        return dumps(self.update_flow(cherrypy.request.body.read().strip()))

    def update_flow(self, jsdata):

        cdb = database('campaigns')
        db = database(self.db_name)
        data = loads(jsdata)
        if not '_rev' in data:
            return {"results": "Cannot update without _rev"}
        try:
            f = flow(json_input=data)
        except flow.IllegalAttributeName as ex:
            return {"results": str(ex)}

        if not f.get_attribute('prepid') and not f.get_attribute('_id'):
            self.logger.error('prepid returned was None')
            raise ValueError('Prepid returned was None')

        # find out what is the change
        old = db.get(f.get_attribute('_id'))

        #uniquing the allowed campaigns if passed duplicates by mistake
        if len(list(set(f.get_attribute('allowed_campaigns')))) != f.get_attribute('allowed_campaigns'):
            f.set_attribute('allowed_campaigns', list(set(f.get_attribute('allowed_campaigns'))))

        nc = f.get_attribute('next_campaign')
        result = self.are_campaigns_correct(nc, f.get_attribute('allowed_campaigns'), cdb)
        if result is not True:
            return result

        ## adjust the requests parameters based on what was provided as next campaign
        self.set_default_request_parameters(nc, cdb, f)

        # update history
        f.update_history({'action': 'update'})

        # save to db
        if not db.update(f.json()):
            self.logger.error('Could not update flow {0}.'.format(f.get_attribute('_id')))
            return {'results': False}

        return self.update_derived_objects(old, f.json())


class DeleteFlow(RESTResource):
    def __init__(self):
        self.db_name = 'flows'

    def DELETE(self, *args):
        """
        Delete a flow and all related objects
        """
        if not args:
            return dumps({"results": 'Error: No Arguments were provided.'})
        return dumps(self.delete_flow(args[0]))

    def delete_flow(self, fid):

        fdb = database(self.db_name)
        ccdb = database('chained_campaigns')
        cdb = database('campaigns')
        # delete all chained campaigns with this flow
        ## exception can be thrown on impossibility of removing
        try:
            self.delete_chained_campaigns(fid, ccdb)
        except Exception as ex:
            return {'results': str(ex)}

        # update relevant campaigns
        try:
            self.update_campaigns(fid, fdb, cdb, ccdb)
        except Exception as ex:
            return {'results': str(ex)}

        return {"results": fdb.delete(fid)}


    def delete_chained_campaigns(self, fid, ccdb):
        # get all campaigns that contain the flow : fid
        ccamps = ccdb.queries(['contains==%s' % fid])

        # check that all relelvant chained campaigns are empty
        crdb = database('chained_requests')
        for cc in ccamps:
            mcm_crs = crdb.queries(['member_of_campaign==%s' % (cc['prepid'])])
            if len(mcm_crs) != 0:
                raise Exception('Impossible to delete flow %s, since %s is not an empty chained campaign' % (fid,
                                                                                                             cc[
                                                                                                                 'prepid']))

        ## all chained campaigns are empty : 
        #=> remove them one by one
        for cc in ccamps:
            ccdb.delete(cc['prepid'])


    def update_campaigns(self, fid, fdb, cdb, ccdb):
        # get the flow
        f = fdb.get(fid)

        next_c = f['next_campaign']
        # get all campaigns that contain the flow's next campaign in the campaign's next
        camps = cdb.queries(['next==%s' % next_c])

        for c in camps:
            ##check that nothing allows to flow in it
            # get the list of chained campaign that still contain both 
            mcm_ccs = ccdb.queries(['contains==' + c['prepid'], 'contains==' + next_c])
            if not len(mcm_ccs):
                #there a no chained campaign left, that uses both that campaign and next_c
                c['next'].remove(fid)
                try:
                    cdb.update(c)
                except Exception as ex:
                    return {'results': str(ex)}


class GetFlow(RESTResource):
    def __init__(self):
        self.db_name = 'flows'

    def GET(self, *args):
        """
        Retrieve the json content of a given flow id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": {}})
        return dumps(self.get_request(args[0]))

    def get_request(self, data):
        db = database(self.db_name)
        return {"results": db.get(prepid=data)}


class ApproveFlow(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self, *args):
        """
        Move the given flow id to the next approval /flow_id , or the provided index /flow_id/index
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})
        if len(args) == 1:
            return dumps(self.multiple_approve(args[0]))
        return dumps(self.multiple_approve(args[0], int(args[1])))


    def multiple_approve(self, rid, val=-1):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.approve(r, val))
            return res
        else:
            return self.approve(rid, val)

    def approve(self, rid, val):
        db = database('flows')
        if not db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given flow id does not exist.'}
        f = flow(json_input=db.get(rid))

        try:
            f.approve(int(val))
        except:
            return {"prepid": rid, "results": False}

        return {"prepid": rid, "results": db.update(f.json())}
