#!/usr/bin/env python
# $Id: $

from socket import gethostbyaddr, herror
from string import split
from syslog import syslog, LOG_INFO, LOG_ERR
from sys import exc_info
from time import time
from traceback import extract_tb
from ConfigParser import ConfigParser

from elementtree.ElementTree import Element, tostring

from Bcfg2.Core import Core
from Bcfg2.Metadata import MetadataStore

from sss.restriction import DataSet, Data
from sss.server import Server

class BcfgServer(Server):
    __implementation__ = 'Bcfg2'
    __component__ = 'bcfg2'
    __dispatch__ = {'get-config':'BuildConfig', 'get-probes':'GetProbes', 'probe-data':'CommitProbeData'}
    __validate__ = 0
        
    def __setup__(self):
        c = ConfigParser()
        c.read(['/home/desai/dev/bcfg2/bcfg2.conf'])
        repo = c.get('server','repository')
        generators = split(c.get('server','generators'),',')
        structures = split(c.get('server', 'structures'),',')
        mpath = c.get('server','metadata')
        self.core = Core(repo, structures, generators)
        self.metadata = MetadataStore("%s/metadata.xml"%(mpath), self.core.fam)
        self.__progress__()

    def __progress__(self):
        while self.core.fam.fm.pending():
            self.core.fam.HandleEvent()
        return 0

    def GetMetadata(self, client):
        if self.metadata.clients.has_key(client):
            return self.metadata.clients[client]
        else:
            syslog(LOG_INFO, "Inserting default metadata for client %s"%(client))
            pass

    def BuildConfig(self, xml, (peer,port)):
        try:
            client = gethostbyaddr(peer)[0].split('.')[0]
        except herror:
            return Element("error", type='host resolution error')
        t = time()
        config = Element("Configuration", version='2.0')
        # get metadata for host
        m = self.GetMetadata(client)
        try:
            structures = self.core.GetStructures(m)
        except:
            self.LogFailure("GetStructures")
            return Element("error", type='structure error')
        for s in structures:
            try:
                self.core.BindStructure(s, m)
                config.append(s)
            except:
                self.LogFailure("BindStructure")
            #for x in s.getchildren():
            #    print x.attrib['name'], '\000' in tostring(x)
        syslog(LOG_INFO, "Generated config for %s in %s seconds"%(client, time()-t))
        return config

    def GetProbes(self, xml, (peer,port)):
        r = Element('probes')
        try:
            client = gethostbyaddr(peer)[0].split('.')[0]
        except herror:
            return Element("error", type='host resolution error')
        m = self.GetMetadata(client)
        for g in self.core.generators:
            for p in g.GetProbes(m):
                r.append(p)
        return r

    def CommitProbeData(self, xml, (peer,port)):
        try:
            client = gethostbyaddr(peer)[0].split('.')[0]
        except herror:
            return Element("error", type='host resolution error')
        for data in xml.findall(".//probe-data"):
            try:
                [g] = [x for x in self.core.generators if x.__name__ == data.attrib['source']]
                g.AcceptProbeData(client, data)
            except:
                self.LogFailure("CommitProbeData")
        return Element("OK")

    def LogFailure(self, failure):
        (t,v,tb)=exc_info()
        syslog(LOG_ERR, "Unexpected failure in %s"%(failure))
        for line in extract_tb(tb):
            syslog(LOG_ERR, '  File "%s", line %i, in %s\n    %s\n'%line)
        syslog(LOG_ERR, "%s: %s\n"%(t,v))
        del t,v,tb

if __name__ == '__main__':
    server = BcfgServer()
    for i in range(10):
        server.__progress__()
