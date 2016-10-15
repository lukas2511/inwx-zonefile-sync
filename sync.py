#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import os

import inwx.inwx
import inwx.configuration
import dns.zone

NS = ['a.xnameserver.de', 'b.xnameserver.de', 'c.xnameserver.de', 'd.xnameserver.org', 'e.xnameserver.biz']

def dns_name_to_text(name, dnsorigin):
	return name.derelativize(origin=dnsorigin).to_text().rstrip('.')

def dns_item_to_record(dataset, item, dnsorigin, key):
	record = {}

	if dataset.rdtype == dns.rdatatype.A:
		record['content'] = item.address
		record['type'] = 'A'
	elif dataset.rdtype == dns.rdatatype.AAAA:
		record['content'] = item.address
		record['type'] = 'AAAA'
	elif dataset.rdtype == dns.rdatatype.MX:
		record['content'] = dns_name_to_text(item.exchange, dnsorigin=dnsorigin)
		record['prio'] = item.preference
		record['type'] = 'MX'
	elif dataset.rdtype == dns.rdatatype.SRV:
		weight = item.weight
		port = item.port
		target = dns_name_to_text(item.target, dnsorigin=dnsorigin)
		record['content'] = "%d %d %s" % (weight, port, target)
		record['prio'] = item.priority
		record['type'] = 'SRV'
	elif dataset.rdtype == dns.rdatatype.TXT:
		record['content'] = " ".join([x.decode('ascii') for x in item.strings])
		record['type'] = 'TXT'
	elif dataset.rdtype == dns.rdatatype.CNAME:
		record['content'] = dns_name_to_text(item.target, dnsorigin=dnsorigin)
		record['type'] = 'CNAME'
	elif dataset.rdtype == dns.rdatatype.NS:
		record['content'] = dns_name_to_text(item.target, dnsorigin=dnsorigin)
		record['type'] = 'NS'
	elif dataset.rdtype == dns.rdatatype.PTR:
		record['content'] = dns_name_to_text(item.target, dnsorigin=dnsorigin)
		record['type'] = 'PTR'
	elif dataset.rdtype == dns.rdatatype.SSHFP:
		record['content'] = item.to_text()
		record['type'] = 'SSHFP'
	else:
		raise Exception("Unknown item type: %r" % item)

	record['name'] = dns_name_to_text(key, dnsorigin)
	record['ttl'] = dataset.ttl

	return record

def sync_zone(inwx_conn, origin, zone):
	print(origin)

	dnsorigin = dns.name.from_text(origin, origin=dns.name.empty)

	# create zone
	checkRet = inwx_conn.nameserver.list({'domain': origin})
	if not checkRet['resData']['domains']:
		print(" + Creating a new zone for %s" % origin)
		inwx_conn.nameserver.create({'domain': origin, 'type': 'MASTER', 'ns': NS})

	apizone = inwx_conn.nameserver.info({'domain': origin})['resData']['record']

	# remove old entries from inwx nameserver
	for record in apizone:
		name = '@' if record['name'] == origin else record['name'].rsplit(".%s" % origin, 1)[0]

		if record['type'] == 'NS' and name == '@':  # do not touch NS records on root of zone
			continue
		elif not dns.name.from_text(name, origin=dns.name.empty) in zone:
			print(" + Deleting record from %s (%r)" % (origin, record))
			inwx_conn.nameserver.deleteRecord({'id': record['id']})
			continue
		elif record['type'] not in ['A', 'AAAA', 'MX', 'SRV', 'TXT', 'CNAME', 'NS', 'PTR', 'SSHFP']:
			continue

		found = False

		for key in zone.keys():
			for dataset in zone[key].rdatasets:
				if dataset.ttl != record['ttl']:
					continue

				if dataset.rdtype in [dns.rdatatype.SOA]:
					continue

				for item in dataset.items:
					tmprecord = dns_item_to_record(dataset, item, dnsorigin, key)

					found = True
					for reckey in tmprecord:
						if tmprecord[reckey] != record[reckey]:
							found = False
							break
					if found:
						break
				if found:
					break
			if found:
				break

		if not found:
			print(" + Deleting record from %s (%r)" % (origin, record))
			inwx_conn.nameserver.deleteRecord({'id': record['id']})

	# create new entries from zonefile
	for key in zone.keys():
		for dataset in zone[key].rdatasets:
			for item in dataset.items:
				if dataset.rdtype in [dns.rdatatype.SOA]:
					continue

				# do not touch nameservers on root of zone
				if key.to_text() == '@' and dataset.rdtype == dns.rdatatype.NS:
					continue

				found = False
				tmprecord = dns_item_to_record(dataset, item, dnsorigin, key)

				for record in apizone:
					found = True
					for reckey in tmprecord:
						if tmprecord[reckey] != record[reckey]:
							found = False
							break
					if found:
						break

				if not found:
					print(" + Creating record on %s (%r)" % (origin, tmprecord))
					tmprecord['domain'] = origin
					inwx_conn.nameserver.createRecord(tmprecord)

	# update soa
	apizonesoa = list(record for record in apizone if record['name'] == origin and record['type'] == 'SOA')[0]
	split_apizonesoa = apizonesoa['content'].split()
	zonesoa_rname = dns_name_to_text(list(dataset for dataset in zone['@'].rdatasets if dataset.rdtype == dns.rdatatype.SOA)[0].items[0].rname, dnsorigin)

	if split_apizonesoa[0] != NS[0] or split_apizonesoa[1] != zonesoa_rname:
		print(" + Updating SOA record on %s (%r)" % (origin, apizonesoa))
		apizonesoa['content'] = "%s %s %s" % (NS[0], zonesoa_rname, split_apizonesoa[2])
		inwx_conn.nameserver.updateRecord(apizonesoa)

def main():
	api_url, username, password, shared_secret = inwx.configuration.get_account_data(True, config_section='live')
	inwx_conn = inwx.inwx.domrobot(api_url, False)
	loginRet = inwx_conn.account.login({'lang': 'en', 'user': username, 'pass': password})

	if 'tfa' in loginRet['resData'] and loginRet['resData']['tfa'] == 'GOOGLE-AUTH':
		loginRet = inwx_conn.account.unlock({'tan': inwx.inwx.getOTP(shared_secret)})

	for zonefile in glob.glob("zones/*"):
		origin = os.path.basename(zonefile)
		zone = dns.zone.from_file(zonefile, origin=origin)
		sync_zone(inwx_conn, origin, zone)


if __name__ == '__main__':
	main()
