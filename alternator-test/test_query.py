# -*- coding: utf-8 -*-
# Tests for the Query operation

import random
import pytest
from botocore.exceptions import ClientError
from decimal import Decimal
from util import random_string, random_bytes, full_query, multiset

# Test that scanning works fine with in-stock paginator
def test_query_basic_restrictions(dynamodb, filled_test_table):
    test_table, items = filled_test_table
    paginator = dynamodb.meta.client.get_paginator('query')

    # EQ
    got_items = []
    for page in paginator.paginate(TableName=test_table.name, KeyConditions={
            'p' : {'AttributeValueList': ['long'], 'ComparisonOperator': 'EQ'}
        }):
        got_items += page['Items']
    print(got_items)
    assert multiset([item for item in items if item['p'] == 'long']) == multiset(got_items)

    # LT
    got_items = []
    for page in paginator.paginate(TableName=test_table.name, KeyConditions={
            'p' : {'AttributeValueList': ['long'], 'ComparisonOperator': 'EQ'},
            'c' : {'AttributeValueList': ['12'], 'ComparisonOperator': 'LT'}
        }):
        got_items += page['Items']
    print(got_items)
    assert multiset([item for item in items if item['p'] == 'long' and item['c'] < '12']) == multiset(got_items)

    # LE
    got_items = []
    for page in paginator.paginate(TableName=test_table.name, KeyConditions={
            'p' : {'AttributeValueList': ['long'], 'ComparisonOperator': 'EQ'},
            'c' : {'AttributeValueList': ['14'], 'ComparisonOperator': 'LE'}
        }):
        got_items += page['Items']
    print(got_items)
    assert multiset([item for item in items if item['p'] == 'long' and item['c'] <= '14']) == multiset(got_items)

    # GT
    got_items = []
    for page in paginator.paginate(TableName=test_table.name, KeyConditions={
            'p' : {'AttributeValueList': ['long'], 'ComparisonOperator': 'EQ'},
            'c' : {'AttributeValueList': ['15'], 'ComparisonOperator': 'GT'}
        }):
        got_items += page['Items']
    print(got_items)
    assert multiset([item for item in items if item['p'] == 'long' and item['c'] > '15']) == multiset(got_items)

    # GE
    got_items = []
    for page in paginator.paginate(TableName=test_table.name, KeyConditions={
            'p' : {'AttributeValueList': ['long'], 'ComparisonOperator': 'EQ'},
            'c' : {'AttributeValueList': ['14'], 'ComparisonOperator': 'GE'}
        }):
        got_items += page['Items']
    print(got_items)
    assert multiset([item for item in items if item['p'] == 'long' and item['c'] >= '14']) == multiset(got_items)

    # BETWEEN
    got_items = []
    for page in paginator.paginate(TableName=test_table.name, KeyConditions={
            'p' : {'AttributeValueList': ['long'], 'ComparisonOperator': 'EQ'},
            'c' : {'AttributeValueList': ['155', '164'], 'ComparisonOperator': 'BETWEEN'}
        }):
        got_items += page['Items']
    print(got_items)
    assert multiset([item for item in items if item['p'] == 'long' and item['c'] >= '155' and item['c'] <= '164']) == multiset(got_items)

    # BEGINS_WITH
    got_items = []
    for page in paginator.paginate(TableName=test_table.name, KeyConditions={
            'p' : {'AttributeValueList': ['long'], 'ComparisonOperator': 'EQ'},
            'c' : {'AttributeValueList': ['11'], 'ComparisonOperator': 'BEGINS_WITH'}
        }):
        print([item for item in items if item['p'] == 'long' and item['c'].startswith('11')])
        got_items += page['Items']
    print(got_items)
    assert multiset([item for item in items if item['p'] == 'long' and item['c'].startswith('11')]) == multiset(got_items)

def test_begins_with(dynamodb, test_table):
    paginator = dynamodb.meta.client.get_paginator('query')
    items = [{'p': 'unorthodox_chars', 'c': sort_key, 'str': 'a'} for sort_key in [u'ÿÿÿ', u'cÿbÿ', u'cÿbÿÿabg'] ]
    with test_table.batch_writer() as batch:
        for item in items:
            batch.put_item(item)

    # TODO(sarna): Once bytes type is supported, /xFF character should be tested
    got_items = []
    for page in paginator.paginate(TableName=test_table.name, KeyConditions={
            'p' : {'AttributeValueList': ['unorthodox_chars'], 'ComparisonOperator': 'EQ'},
            'c' : {'AttributeValueList': [u'ÿÿ'], 'ComparisonOperator': 'BEGINS_WITH'}
        }):
        got_items += page['Items']
    print(got_items)
    assert sorted([d['c'] for d in got_items]) == sorted([d['c'] for d in items if d['c'].startswith(u'ÿÿ')])

    got_items = []
    for page in paginator.paginate(TableName=test_table.name, KeyConditions={
            'p' : {'AttributeValueList': ['unorthodox_chars'], 'ComparisonOperator': 'EQ'},
            'c' : {'AttributeValueList': [u'cÿbÿ'], 'ComparisonOperator': 'BEGINS_WITH'}
        }):
        got_items += page['Items']
    print(got_items)
    assert sorted([d['c'] for d in got_items]) == sorted([d['c'] for d in items if d['c'].startswith(u'cÿbÿ')])

# Items returned by Query should be sorted by the sort key. The following
# tests verify that this is indeed the case, for the three allowed key types:
# strings, binary, and numbers. These tests test not just the Query operation,
# but inherently that the sort-key sorting works.
def test_query_sort_order_string(test_table):
    # Insert a lot of random items in one new partition:
    # str(i) has a non-obvious sort order (e.g., "100" comes before "2") so is a nice test.
    p = random_string()
    items = [{'p': p, 'c': str(i)} for i in range(128)]
    with test_table.batch_writer() as batch:
        for item in items:
            batch.put_item(item)
    got_items = full_query(test_table, KeyConditions={'p': {'AttributeValueList': [p], 'ComparisonOperator': 'EQ'}})
    assert len(items) == len(got_items)
    # Extract just the sort key ("c") from the items
    sort_keys = [x['c'] for x in items]
    got_sort_keys = [x['c'] for x in got_items]
    # Verify that got_sort_keys are already sorted (in string order)
    assert sorted(got_sort_keys) == got_sort_keys
    # Verify that got_sort_keys are a sorted version of the expected sort_keys
    assert sorted(sort_keys) == got_sort_keys
def test_query_sort_order_bytes(test_table_sb):
    # Insert a lot of random items in one new partition:
    # We arbitrarily use random_bytes with a random length.
    p = random_string()
    items = [{'p': p, 'c': random_bytes(10)} for i in range(128)]
    with test_table_sb.batch_writer() as batch:
        for item in items:
            batch.put_item(item)
    got_items = full_query(test_table_sb, KeyConditions={'p': {'AttributeValueList': [p], 'ComparisonOperator': 'EQ'}})
    assert len(items) == len(got_items)
    sort_keys = [x['c'] for x in items]
    got_sort_keys = [x['c'] for x in got_items]
    # Boto3's "Binary" objects are sorted as if bytes are signed integers.
    # This isn't the order that DynamoDB itself uses (byte 0 should be first,
    # not byte -128). Sorting the byte array ".value" works.
    assert sorted(got_sort_keys, key=lambda x: x.value) == got_sort_keys
    assert sorted(sort_keys) == got_sort_keys
def test_query_sort_order_number(test_table_sn):
    # This is a list of numbers, sorted in correct order, and each suitable
    # for accurate representation by Alternator's number type.
    numbers = [
        Decimal("-2e10"),
        Decimal("-7.1e2"),
        Decimal("-4.1"),
        Decimal("-0.1"),
        Decimal("-1e-5"),
        Decimal("0"),
        Decimal("2e-5"),
        Decimal("0.15"),
        Decimal("1"),
        Decimal("1.00000000000000000000000001"),
        Decimal("3.14159"),
        Decimal("3.1415926535897932384626433832795028841"),
        Decimal("31.4"),
        Decimal("1.4e10"),
    ]
    # Insert these numbers, in random order, into one partition:
    p = random_string()
    items = [{'p': p, 'c': num} for num in random.sample(numbers, len(numbers))]
    with test_table_sn.batch_writer() as batch:
        for item in items:
            batch.put_item(item)
    # Finally, verify that we get back exactly the same numbers (with identical
    # precision), and in their original sorted order.
    got_items = full_query(test_table_sn, KeyConditions={'p': {'AttributeValueList': [p], 'ComparisonOperator': 'EQ'}})
    got_sort_keys = [x['c'] for x in got_items]
    assert got_sort_keys == numbers

def test_query_filtering_attributes_equality(filled_test_table):
    test_table, items = filled_test_table

    query_filter = {
        "attribute" : {
            "AttributeValueList" : [ "xxxx" ],
            "ComparisonOperator": "EQ"
        }
    }
    got_items = full_query(test_table, KeyConditions={'p': {'AttributeValueList': ['long'], 'ComparisonOperator': 'EQ'}}, QueryFilter=query_filter)
    print(got_items)
    assert multiset([item for item in items if item['p'] == 'long' and item['attribute'] == 'xxxx']) == multiset(got_items)

    query_filter = {
        "attribute" : {
            "AttributeValueList" : [ "xxxx" ],
            "ComparisonOperator": "EQ"
        },
        "another" : {
            "AttributeValueList" : [ "yy" ],
            "ComparisonOperator": "EQ"
        }
    }

    got_items = full_query(test_table, KeyConditions={'p': {'AttributeValueList': ['long'], 'ComparisonOperator': 'EQ'}}, QueryFilter=query_filter)
    print(got_items)
    assert multiset([item for item in items if item['p'] == 'long' and item['attribute'] == 'xxxx' and item['another'] == 'yy']) == multiset(got_items)

# Test Query with the AttributesToGet parameter. Result should include the
# selected attributes only - if one wants the key attributes as well, one
# needs to select them explicitly. When no key attributes are selected,
# some items may have *none* of the selected attributes. Those items are
# returned too, as empty items - they are not outright missing.
def test_query_attributes_to_get(dynamodb, test_table):
    p = random_string()
    items = [{'p': p, 'c': str(i), 'a': str(i*10), 'b': str(i*100) } for i in range(10)]
    with test_table.batch_writer() as batch:
        for item in items:
            batch.put_item(item)
    for wanted in [ ['a'],             # only non-key attributes
                    ['c', 'a'],        # a key attribute (sort key) and non-key
                    ['p', 'c'],        # entire key
                    ['nonexistent']    # none of the items have this attribute!
                   ]:
        got_items = full_query(test_table, KeyConditions={'p': {'AttributeValueList': [p], 'ComparisonOperator': 'EQ'}}, AttributesToGet=wanted)
        expected_items = [{k: x[k] for k in wanted if k in x} for x in items]
        assert multiset(expected_items) == multiset(got_items)