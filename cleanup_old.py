"""Delete old duplicate profiles from DynamoDB."""
import boto3

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('rural-credit-profiles')

old_ids = [
    '11185de2-e1ac-4e41-b906-07c0a2eb2bc3',
    '39dd0cf4-e4c9-4f0c-8137-ce53eedd2eea',
    '475830c1-54e7-45f3-ba97-f7c9cce86182',
    '4ca13649-9b07-4ec4-9746-56bbb813e0e5',
    'a4ea9ff0-3207-48ed-9069-e95d6df8d8de',
]

# Scan all items
resp = table.scan()
items = resp['Items']
while resp.get('LastEvaluatedKey'):
    resp = table.scan(ExclusiveStartKey=resp['LastEvaluatedKey'])
    items.extend(resp['Items'])

print(f"Total items in profiles table: {len(items)}")
deleted = 0
for item in items:
    pk = item.get('PK', '')
    sk = item.get('SK', '')
    profile_id = item.get('profile_id', pk.replace('PROFILE#', ''))
    name = item.get('name', '?')
    is_old = profile_id in old_ids
    tag = " ** DELETING **" if is_old else ""
    print(f"  PK={pk}  SK={sk}  name={name}{tag}")
    if is_old:
        table.delete_item(Key={'PK': pk, 'SK': sk})
        deleted += 1

# Also check for items keyed on profile_id directly (no PK/SK)
for item in items:
    if 'PK' not in item and 'profile_id' in item:
        pid = item['profile_id']
        if pid in old_ids:
            print(f"  Deleting by profile_id key: {pid}")
            table.delete_item(Key={'profile_id': pid})
            deleted += 1

resp2 = table.scan(Select='COUNT')
print(f"\nDeleted: {deleted}")
print(f"Remaining items: {resp2['Count']}")
