import re
import argparse
import os
import glob
import plotly.graph_objects as go

def get_latest_log_file():
    list_of_files = glob.glob('logs/*_worker_*.log.txt')
    if not list_of_files:
        return None
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file

def parse_log(logfile):
    events = {} # node_id -> list of (asn, event_type)
    on_periods = {} # node_id -> list of (start_asn, duration)
    current_on = {} # node_id -> start_asn

    with open(logfile, 'r') as f:
        for line in f:
            m_node = re.search(r'Node_(\d+)', line)
            if not m_node:
                continue
            
            node = int(m_node.group(1))
            if node not in events:
                events[node] = []
                on_periods[node] = []

            m_on = re.search(r'turned ON at ASN (\d+)', line)
            if m_on:
                asn = int(m_on.group(1))
                current_on[node] = asn
                events[node].append((asn, 'ON'))
                continue

            m_off = re.search(r'turned OFF at ASN (\d+)', line)
            if m_off:
                asn = int(m_off.group(1))
                if node in current_on:
                    on_periods[node].append((current_on[node], asn - current_on[node]))
                    del current_on[node]
                events[node].append((asn, 'OFF'))
                continue

            m_scan = re.search(r'performing SCAN at ASN (\d+)', line)
            if m_scan:
                asn = int(m_scan.group(1))
                events[node].append((asn, 'SCAN'))
                continue

            m_adv = re.search(r'performing ADV at ASN (\d+)', line)
            if m_adv:
                asn = int(m_adv.group(1))
                events[node].append((asn, 'ADV'))
                continue
            
            m_succ = re.search(r'got ADV success at ASN (\d+)', line)
            if m_succ:
                asn = int(m_succ.group(1))
                events[node].append((asn, 'SUCCESS'))
                continue

    # Close any open ON periods
    for node, start_asn in current_on.items():
        if events[node]:
            last_asn = events[node][-1][0]
            if last_asn > start_asn:
                on_periods[node].append((start_asn, last_asn - start_asn))

    return events, on_periods

def visualize(events, on_periods, output_file):
    fig = go.Figure()
    
    nodes = sorted(events.keys())
    
    y_tickvals = []
    y_ticktexts = []
    
    all_shapes = []
    for i, node in enumerate(nodes):
        y_pos = i
        y_tickvals.append(y_pos)
        
        is_find = len(nodes) > 1 and node >= len(nodes) // 2
        protocol_name = "Find" if is_find else "BFND"
        y_ticktexts.append(f'Node {node}<br>({protocol_name})')
        
        # Plot ON periods as shapes
        if node in on_periods:
            for start_asn, duration in on_periods[node]:
                end_asn = start_asn + duration
                all_shapes.append(dict(
                    type="rect",
                    x0=start_asn, y0=y_pos - 0.3,
                    x1=end_asn, y1=y_pos + 0.3,
                    fillcolor="rgba(0, 200, 0, 0.2)",
                    line=dict(width=0),
                    layer="below"
                ))

        scans_x = [e[0] for e in events[node] if e[1] == 'SCAN']
        advs_x = [e[0] for e in events[node] if e[1] == 'ADV']
        succs_x = [e[0] for e in events[node] if e[1] == 'SUCCESS']

        if scans_x:
            fig.add_trace(go.Scatter(
                x=scans_x, y=[y_pos]*len(scans_x),
                mode='markers', marker=dict(symbol='line-ns', color='blue', size=15),
                name='SCAN',
                legendgroup='SCAN',
                showlegend=True if i==0 else False,
                hoverinfo='x+name'
            ))
            
        if advs_x:
            fig.add_trace(go.Scatter(
                x=advs_x, y=[y_pos]*len(advs_x),
                mode='markers', marker=dict(symbol='star', color='red', size=15),
                name='ADV',
                legendgroup='ADV',
                showlegend=True if i==0 else False,
                hoverinfo='x+name'
            ))
            
        if succs_x:
            fig.add_trace(go.Scatter(
                x=succs_x, y=[y_pos]*len(succs_x),
                mode='markers', marker=dict(symbol='x', color='darkgreen', size=25),
                name='SUCCESS',
                legendgroup='SUCCESS',
                showlegend=True if i==0 else False,
                hoverinfo='x+name'
            ))

    fig.update_layout(
        title='Interactive Protocol Event Swimlanes',
        xaxis_title='Simulation Time (ASN / ms)',
        yaxis_title='Nodes',
        yaxis=dict(
            tickmode='array',
            tickvals=y_tickvals,
            ticktext=y_ticktexts,
            range=[-0.5, len(nodes) - 0.5]
        ),
        hovermode='closest',
        template='plotly_white'
    )
    
    # Add dummy trace for ON period legend
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        marker=dict(symbol='square', color='rgba(0, 200, 0, 0.2)', size=15),
        name='ON period'
    ))
    fig.update_layout(shapes=all_shapes)
    fig.write_html(output_file)
    print(f"Interactive visualization saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize BFND Simulator Debug Logs Interactively")
    parser.add_argument('--log_file', type=str, default=None, help="Path to the worker log file")
    parser.add_argument('--output', type=str, default='log_visualization.html', help="Output HTML file")
    args = parser.parse_args()

    logfile = args.log_file
    if not logfile:
        logfile = get_latest_log_file()
        if not logfile:
            print("Error: No worker log files found in logs/")
            exit(1)
            
    print(f"Parsing log file: {logfile}")
    events, on_periods = parse_log(logfile)
    visualize(events, on_periods, args.output)
