#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# code mostly stolen from Dennis Kaarsemaker (see https://github.com/rthalley/dnspython/blob/master/examples/zonediff.py)

# i use this to verify my zones are imported correctly
# run sync.py, afterwards login to inwx web interface, go to nameservers, and you can download an axfr dump / zonefile

# usage: python3 diff.py example.com zones/example.com ~/Downloads/example.com_zone.txt

import dns.zone
import sys

def diff_zones(zone1, zone2, ignore_ttl=False, ignore_soa=False):
	"""diff_zones(zone1, zone2, ignore_ttl=False, ignore_soa=False) -> changes
	Compares two dns.zone.Zone objects and returns a list of all changes
	in the format (name, oldnode, newnode).
	If ignore_ttl is true, a node will not be added to this list if the
	only change is its TTL.
	If ignore_soa is true, a node will not be added to this list if the
	only changes is a change in a SOA Rdata set.
	The returned nodes do include all Rdata sets, including unchanged ones.
	"""

	changes = []
	for name in zone1:
		name = str(name)
		n1 = zone1.get_node(name)
		n2 = zone2.get_node(name)
		if not n2:
			changes.append((str(name), n1, n2))
		elif _nodes_differ(n1, n2, ignore_ttl, ignore_soa):
			changes.append((str(name), n1, n2))

	for name in zone2:
		n1 = zone1.get_node(name)
		if not n1:
			n2 = zone2.get_node(name)
			changes.append((str(name), n1, n2))
	return changes

def _nodes_differ(n1, n2, ignore_ttl, ignore_soa):
	if ignore_soa or not ignore_ttl:
		# Compare datasets directly
		for r in n1.rdatasets:
			if ignore_soa and r.rdtype == dns.rdatatype.SOA:
				continue
			if r not in n2.rdatasets:
				return True
			if not ignore_ttl:
				return r.ttl != n2.find_rdataset(r.rdclass, r.rdtype).ttl

		for r in n2.rdatasets:
			if ignore_soa and r.rdtype == dns.rdatatype.SOA:
				continue
			if r not in n1.rdatasets:
				return True
	else:
		return n1 != n2

def format_changes_plain(oldf, newf, changes, ignore_ttl=False):
	"""format_changes(oldfile, newfile, changes, ignore_ttl=False) -> str
	Given 2 filenames and a list of changes from diff_zones, produce diff-like
	output. If ignore_ttl is True, TTL-only changes are not displayed"""

	ret = "--- %s\n+++ %s\n" % (oldf, newf)
	for name, old, new in changes:
		ret += "@ %s\n" % name
		if not old:
			for r in new.rdatasets:
				ret += "+ %s\n" % str(r).replace('\n', '\n+ ')
		elif not new:
			for r in old.rdatasets:
				ret += "- %s\n" % str(r).replace('\n', '\n+ ')
		else:
			for r in old.rdatasets:
				if r not in new.rdatasets or (
					r.ttl != new.find_rdataset(r.rdclass, r.rdtype).ttl and
					not ignore_ttl
				):
					ret += "- %s\n" % str(r).replace('\n', '\n+ ')
			for r in new.rdatasets:
				if r not in old.rdatasets or (
					r.ttl != old.find_rdataset(r.rdclass, r.rdtype).ttl and
					not ignore_ttl
				):
					ret += "+ %s\n" % str(r).replace('\n', '\n+ ')
	return ret

origin = sys.argv[1]
revafile = sys.argv[2]
revbfile = sys.argv[3]

reva = dns.zone.from_file(revafile, origin=origin)
revb = dns.zone.from_file(revbfile, origin=origin)

changes = diff_zones(reva, revb, ignore_soa=True)

if not changes:
	print("all good!")
else:
	print(format_changes_plain(revafile, revbfile, changes))
