#Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service Terms and the SOW between the parties dated 15 Nov 2024.
import json
import boto3
import base64
from botocore.exceptions import ClientError
import botocore
import random, time  # Add this import for random number generation
import feedparser
from datetime import datetime
import pytz
import PyRSS2Gen
import os
import secrets

# Constants
RSS_TITLE = "AWS NEWS RSS"
RSS_LINK = "http://www.awsnews.ai"
RSS_DESCRIPTION = "RSS feed for AWS News"
RSS_AUTHOR = "AWS News"
RSS_LANGUAGE = "fr-FR"
BUCKET_NAME = os.environ['BUCKET_NAME']
FLOW_EXECUTION_ROLE_ARN = os.environ['FLOW_EXECUTION_ROLE_ARN']
KEY_NAME = 'awsnews.xml'
KEY_PROCESSED_NAME = 'processed.xml'

def get_secret(secret_name):
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager')
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e
    else:
        if 'SecretString' in get_secret_value_response:
            return json.loads(get_secret_value_response['SecretString'])
        else:
            return json.loads(base64.b64decode(get_secret_value_response['SecretBinary']))

def get_s3_object(s3_client, key):
    """Retrieve an object from S3."""
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
    return response['Body'].read()

def parse_feed(content):
    """Parse RSS feed content."""
    return feedparser.parse(content)

def get_existing_ids(feed):
    """Get a set of existing entry IDs from a feed."""
    return set(entry.id for entry in feed.entries)

def create_rss_item(entry, pub_date=None):
    """Create an RSS item from an entry."""
    return PyRSS2Gen.RSSItem(
        guid=entry.get('id', entry.get('guid')),
        title=entry.get('title'),
        link=entry.get('link'),
        description=entry.get('description'),
        pubDate=pub_date or datetime.strptime(entry.get('published'), "%a, %d %b %Y %H:%M:%S %Z")
    )

def create_rss_feed(items):
    """Create an RSS feed with given items."""
    return PyRSS2Gen.RSS2(
        title=RSS_TITLE,
        link=RSS_LINK,
        description=RSS_DESCRIPTION,
        lastBuildDate=datetime.now(pytz.UTC),
        items=items
    )

def create_prompt_flow(client):
    # Replace with the service role that you created.
    #FLOWS_SERVICE_ROLE = "arn:aws:iam::xxxxxxxxxxxxxxx:role/service-role/AmazonBedrockExecutionRoleForFlows_VHMQ1JP0E8M"

    # Define each node

     # Input node: validates that the content of the InvokeFlow request is a JSON object
    input_node = {
        "type": "Input",
        "name": "FlowInputNode",
        "outputs": [
            {
                "name": "document",
                "type": "String"
            }
        ]
    }


    # Prompt node1: creates a RSS item
    prompt_node1 = {
        "type": "Prompt",
        "name": "AWSNewsScope",
        "configuration": {
            "prompt": {
                "sourceConfiguration": {
                    "inline": {
                        "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
                        "templateType": "TEXT",
                        "inferenceConfiguration": {
                            "text": {
                                "temperature": 0.8
                            }
                        },
                        "templateConfiguration": {
                            "text": {
                                "text": """Task: Analyze the provided AWS RSS news item and categorize it based on specific keywords.

Input: An XML string containing an AWS news item, enclosed in <AWSNewsScope> tags.

Instructions:
1. Parse the XML content within the <AWSNewsScope> tags.
2. Search for the following keywords (case-insensitive):
   ECS, API Gateway, Lambda, VPC Endpoints, S3, Cognito, ALB, WAF, SSM, Bedrock, RDS
3. Categorization:
   - If any of the keywords are present: Respond with "InTheScope"
   - If none of the keywords are present: Respond with "OutOfTheScope"
4. Provide only the categorization result without any additional text.

<AWSNewsScope>
{{AWSNewsScope}}
</AWSNewsScope>"""
                            }
                        }
                    }
                }
            }
        },
        "inputs": [
            {
                "name": "AWSNewsScope",
                "type": "String",
                "expression": "$.data"
            }
        ],
        "outputs": [
            {
                "name": "modelCompletion",
                "type": "String"
            }
        ]
    }


   # Condition node: validates the condition and returns it
    condition_node = {
        "name": "ConditionNode_1",
        "type": "Condition",
        "inputs": [
            {
                "name": "input",
                "type": "String",
                "expression": "$.data"
            }
        ],
        "configuration": {
            "condition": {
                "conditions": [
                    {
                        "name": "InTheScope",
                         "expression": "input == \"InTheScope\""
                    },
                    {
                        "name": "default"
                    }
                ]
            }
        }
    }


    # Prompt node: creates a RSS item
    prompt_node = {
        "type": "Prompt",
        "name": "RSSNews",
        "configuration": {
            "prompt": {
                "sourceConfiguration": {
                    "inline": {
                        "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
                        "templateType": "TEXT",
                        "inferenceConfiguration": {
                            "text": {
                                "temperature": 0.8
                            }
                        },
                        "templateConfiguration": {
                            "text": {
                                "text": """Task: Transform AWS RSS news into a French Teams message and reformat it as an RSS feed item.

Input: An XML string containing AWS news, enclosed in <RSSnews> tags.

Instructions:
1. Parse the content within the <RSSnews> tags.
2. Transform the content into a French message suitable for a large internal project team on Microsoft Teams.
3. Reformat the content into a single RSS feed <item> with the following elements:
   <guid>: Generate a unique identifier
   <title>: Create a concise French title
   <link>: Include the original news link if available
   <description>: Summarize the content in French, limited to 150 words
4. Respond with only the formatted RSS <item> XML, without any additional text.

<RSSnews>
{{RSSnews}}
</RSSnews>"""
                            }
                        }
                    }
                }
            }
        },
        "inputs": [
            {
                "name": "RSSnews",
                "type": "String",
                "expression": "$.data"
            }
        ],
        "outputs": [
            {
                "name": "modelCompletion",
                "type": "String"
            }
        ]
    }

    # Output node: validates the output and returns it
    output_node = {
        "type": "Output",
        "name": "FlowOutput",
        "inputs": [
            {
                "name": "document",
                "type": "String",
                "expression": "$.data"
            }
        ]
    }

    # Create connections between the nodes
    connections = []

    # Create connections between the input node and prompt node1
    for input in prompt_node1["inputs"]:
        connections.append(
            {
                "name": "_".join([input_node["name"], prompt_node1["name"], input["name"]]),
                "source": input_node["name"],
                "target": prompt_node1["name"],
                "type": "Data",
                "configuration": {
                    "data": {
                        "sourceOutput": input_node["outputs"][0]["name"],
                        "targetInput": input["name"]
                    }
                }
            }
        )

    # Create a connection between the output of the prompt node1 and the condition node
    connections.append(
        {
            "name": "_".join([prompt_node1["name"], condition_node["name"]]),
            "source": prompt_node1["name"],
            "target": condition_node["name"],
            "type": "Data",
            "configuration": {
                "data": {
                    "sourceOutput": prompt_node1["outputs"][0]["name"],
                    "targetInput": condition_node["inputs"][0]["name"]
                }
            }
        }
    )

    # Connections from condition_node to downstream prompt node
    connections.append(
        {
            "name": "_".join([condition_node["name"], prompt_node["name"]]),
            "source": condition_node["name"],
            "target": prompt_node["name"],
            "type": "Conditional",
            "configuration": {
                "conditional": {
                    "condition": "default",
                    "condition": condition_node["configuration"]["condition"]["conditions"][0]["name"]
                }
            }
        }
    )

    # Add a separate data connection if needed
    connections.append(
        {
            "name": "_".join([input_node["name"], prompt_node["name"], "data"]),
            "source": input_node["name"],
            "target": prompt_node["name"],
            "type": "Data",
            "configuration": {
                "data": {
                    "sourceOutput": input_node["outputs"][0]["name"],
                    "targetInput": prompt_node["inputs"][0]["name"]
                }
            }
        }
    )

    # Create a connection between the output of the prompt node and the output node
    connections.append(
        {
            "name": "_".join([prompt_node["name"], output_node["name"]]),
            "source": prompt_node["name"],
            "target": output_node["name"],
            "type": "Data",
            "configuration": {
                "data": {
                    "sourceOutput": prompt_node["outputs"][0]["name"],
                    "targetInput": output_node["inputs"][0]["name"]
                }
            }
        }
    )

    flows_response = client.list_flows()
    print (str(flows_response))
    flows = flows_response.get('flowSummaries', [])

    # Iterate through the flows and delete those starting with "AWSNEWS"
    for flow in flows:
        if flow.get('name', '').startswith('AWSNews'):
            flow_id = flow['id']

            flow_aliases_response = client.list_flow_aliases(flowIdentifier=flow_id)
            print ("flow aliases: " + str(flow_aliases_response))
            flow_aliaes = flow_aliases_response.get('flowAliasSummaries', [])
            for flow_alias in flow_aliaes:
                flow_alias_id = flow_alias['id']
                if flow_alias_id != 'TSTALIASID':
                    client.delete_flow_alias(flowIdentifier=flow_id, aliasIdentifier=flow_alias_id)

            try:
                delete_response = client.delete_flow(flowIdentifier=flow_id)
                print(f"Deleted flow: {flow['name']}")
            except client.exceptions.ResourceNotFoundException:
                print(f"Flow {flow['name']} not found.")
            except Exception as e:
                print(f"Error deleting flow {flow['name']}: {e}")


    # Create the flow from the nodes and connections
    #flow_name = f"AWSNews_{random.randint(1000, 9999)}_{int(time.time())}"
    flow_name = f"AWSNews_{secrets.randbelow(9000) + 1000}_{int(time.time())}"
    response = client.create_flow(
        name=flow_name,
        description="A flow that creates a personalised RSS.",
        executionRoleArn=FLOW_EXECUTION_ROLE_ARN,
        definition={
            "nodes": [input_node, prompt_node1, condition_node, prompt_node, output_node],
            "connections": connections
        }
    )

    # Extract and return the flow ID from the response
    flow_id = response.get("id")
    client.prepare_flow(flowIdentifier=flow_id)
    response = client.create_flow_version(flowIdentifier=flow_id)
                                    
    flow_version = response.get("version")
    response = client.create_flow_alias(
        flowIdentifier=flow_id,
        name="latest",
        description="Alias pointing to the latest version of the flow.",
        routingConfiguration=[
            {
                "flowVersion": flow_version
            }
        ]
    )
    
    flow_alias_id = response.get("id")

    FLOW_IDENTIFIER = flow_id
    FLOW_ALIAS_IDENTIFIER = flow_alias_id

    return {
        "statusCode": 200,
        "body": json.dumps({
            "flowId": flow_id,
            "flow_alias_Id": flow_alias_id,
            "message": "Flow created successfully"
        })
    }


def invoke_bedrock_flow(client_runtime, result_flow, input_content):
    #print ("flow id " + FLOW_IDENTIFIER + " " + FLOW_ALIAS_IDENTIFIER)
    
    # Parse the JSON string in the 'body' key
    try:
        body_json = json.loads(result_flow['body'])
        
        # Extract the flowId and flow_alias_Id
        flow_id = body_json['flowId']
        flow_alias_id = body_json['flow_alias_Id']
        
        # Print the extracted values
        print(f"Flow ID: {flow_id}")
        print(f"Flow Alias ID: {flow_alias_id}")
    
        #"""Invoke Bedrock flow and return the result."""

        try:    
            response = client_runtime.invoke_flow(
                flowIdentifier=flow_id,
                flowAliasIdentifier=flow_alias_id,
                inputs=[{
                    "content": {"document": input_content},
                    "nodeName": "FlowInputNode",
                    "nodeOutputName": "document"
                }]
            )
            
            result = {}
            for event in response.get("responseStream"):
                result.update(event)
            
            return result
        except client_runtime.exceptions.ResourceNotFoundException as e:
            print(f"Resource not found error: {str(e)}")
            raise
        except client_runtime.exceptions.ValidationException as e:
            print(f"Validation error: {str(e)}")
            raise
        except client_runtime.exceptions.ThrottlingException as e:
            print(f"Throttling error: {str(e)}")
            raise
        except botocore.exceptions.ClientError as e:
            print(f"Boto3 client error: {str(e)}")
            if e.response['Error']['Code'] == '404':
                print("404 error: The specified flow or flow alias might not exist.")
            raise
        except Exception as e:
            print(f"Unexpected error during flow invocation: {str(e)}")
            raise
        
    except json.JSONDecodeError as e:
        print(f"Error parsing result_flow JSON: {str(e)}")
        raise
    except KeyError as e:
        print(f"Missing key in result_flow: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error in invoke_bedrock_flow: {str(e)}")
        raise

def lambda_handler(event, context):
    try:
        s3 = boto3.client('s3')
        
        # Retrieve FEED_URL from Secrets Manager
        secret_name = os.environ['FEED_URL_SECRET_NAME']
        secret = get_secret(secret_name)
        FEED_URL = secret['FEED_URL']

        # Process existing feeds
        rss_content = get_s3_object(s3, KEY_NAME)
        existing_feed = parse_feed(rss_content)
        existing_ids = get_existing_ids(existing_feed)
        
        rss_processed_content = get_s3_object(s3, KEY_PROCESSED_NAME)
        existing_processed_feed = parse_feed(rss_processed_content)
        existing_processed_ids = get_existing_ids(existing_processed_feed)
        
        # Process new feed
        feed = feedparser.parse(FEED_URL)
        
        new_entries = [entry for entry in feed.entries if entry.id not in existing_processed_ids]
        
        print(str(new_entries))
        
        if not new_entries:
            return {
                'statusCode': 200,
                'body': json.dumps('No new entries found.')
            }
        
        last_entry = new_entries[0]
        recent_updates = f"Id: {last_entry.id} | Title: {last_entry.title} | Link: {last_entry.link} | Description: {last_entry.description} | Published: {last_entry.published}"

        print(recent_updates)
        
        # Update processed feed
        rss_processed_items = [create_rss_item(last_entry, datetime.now())] + [create_rss_item(entry) for entry in existing_processed_feed.entries]
        rss_processed_feed = create_rss_feed(rss_processed_items)
        s3.put_object(Body=rss_processed_feed.to_xml("UTF-8"), Bucket=BUCKET_NAME, Key=KEY_PROCESSED_NAME)
        
        # Invoke Bedrock flow
        client_runtime = boto3.client('bedrock-agent-runtime')
        
        # Create a Bedrock client
        client = boto3.client(service_name='bedrock-agent')

        # Check for existing flows starting with "AWSNews_"
        flows_response = client.list_flows()
        flows = flows_response.get('flowSummaries', [])
        existing_flow = next((flow for flow in flows if flow['name'].startswith('AWSNews_')), None)

        if existing_flow:
            # Use the existing flow
            flow_id = existing_flow['id']
            flow_aliases_response = client.list_flow_aliases(flowIdentifier=flow_id)
            flow_aliases = flow_aliases_response.get('flowAliasSummaries', [])
            flow_alias_id = next((alias['id'] for alias in flow_aliases if alias['name'] == 'latest'), None)

            if not flow_alias_id:
                # Create a new alias if 'latest' doesn't exist
                response = client.create_flow_alias(
                    flowIdentifier=flow_id,
                    name="latest",
                    description="Alias pointing to the latest version of the flow.",
                    routingConfiguration=[
                        {
                            "flowVersion": client.get_flow(flowIdentifier=flow_id)['latestVersion']
                        }
                    ]
                )
                flow_alias_id = response.get("id")

            result_flow = {
                "statusCode": 200,
                "body": json.dumps({
                    "flowId": flow_id,
                    "flow_alias_Id": flow_alias_id,
                    "message": "Existing flow retrieved successfully"
                })
            }
            print(f"Using existing flow: {existing_flow['name']}")
        else:
            # Create a new flow
            result_flow = create_prompt_flow(client)

        print("result_flow: " + str(result_flow))    

        try:
            result = invoke_bedrock_flow(client_runtime, result_flow, recent_updates)
            print("result " +str(result))
            if result['flowCompletionEvent']['completionReason'] == 'SUCCESS':
                input_xml = result['flowOutputEvent']['content']['document']
                new_feed = parse_feed(input_xml)
                new_item = new_feed.entries[0]
                
                # Update main feed
                rss_items = [create_rss_item(new_item, datetime.now())] + [create_rss_item(entry) for entry in existing_feed.entries]
                rss_feed = create_rss_feed(rss_items)
                s3.put_object(Body=rss_feed.to_xml("UTF-8"), Bucket=BUCKET_NAME, Key=KEY_NAME)
            else:
                print("The prompt flow invocation completed because of the following reason:", result['flowCompletionEvent']['completionReason'])
        except Exception as e:
                print(f"Error invoking Bedrock flow: {str(e)}")
                raise    
        return {
            'statusCode': 200,
            'body': json.dumps('RSS feed updated successfully.')
        }
    except Exception as e:
        print(f"Unexpected error in lambda_handler: {str(e)}")
        raise
