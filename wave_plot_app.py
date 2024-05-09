import streamlit as st
import fdasrsf as fs
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
import os
import tempfile
from scipy.interpolate import CubicSpline
import plotly.graph_objects as go
import struct
import datetime
from skfda import FDataGrid
from skfda.preprocessing.dim_reduction import FPCA
from sklearn.cluster import DBSCAN
from kneed import KneeLocator
from sklearn.neighbors import NearestNeighbors
from scipy.ndimage import gaussian_filter1d
import warnings
warnings.filterwarnings('ignore')

def plot_scatter_waves(df, freq, db, background_curves=False, smoothing_method='None', sigma=3, n=15):
    fig = go.Figure()
    khz = df[(df['Freq(Hz)'].astype(float) == freq) & (df['Level(dB)'].astype(float) == db)]
    
    if not khz.empty:
        index = khz.index.values[0]
        final = df.loc[index, '0':]
        final = pd.to_numeric(final, errors='coerce')

        # Find highest peaks separated by at least n data points
        peaks, _ = find_peaks(final, distance=n)
        highest_peaks = peaks[np.argsort(final[peaks])[-5:]]

        if multiply_y_factor != 1:
            y_values = final * multiply_y_factor
        else:
            y_values = final

        fig.update_layout(width=700, height=450)

        # Plot scatter plot instead of line plot
        fig.add_trace(go.Scatter(x=np.arange(len(final)), y=y_values, mode='markers', name='Scatter Plot'))

        # Mark the highest peaks with red markers
        fig.add_trace(go.Scatter(x=highest_peaks, y=y_values[highest_peaks], mode='markers', marker=dict(color='red'), name='Peaks'))

        # Annotate the peaks with red color, smaller font, and closer to the peaks
        for peak in highest_peaks:
            fig.add_annotation(
                x=peak,
                y=y_values[peak],
                text=f'{y_values[peak]:.4f}',
                showarrow=True,
                arrowhead=2,
                arrowcolor='red',
                arrowwidth=2,
                ax=0,
                ay=-30,
                font=dict(color='red', size=10)
            )

    return fig

def plotting_waves_cubic_spline(df, freq=16000, db=90, n=45):
    fig = go.Figure()
    i=0
    for df in dfs:
        khz = df[df['Freq(Hz)'] == freq]
        dbkhz = khz[khz['Level(dB)'] == db]
        if not khz.empty:
            index = dbkhz.index.values[0]
            original_waveform = df.loc[index, '0':].dropna()
            original_waveform = pd.to_numeric(original_waveform, errors='coerce')[:-1]

            if multiply_y_factor != 1:
                original_waveform *= multiply_y_factor

            # Apply cubic spline interpolation
            smooth_time = np.linspace(0, len(original_waveform) - 1, 244)
            cs = CubicSpline(np.arange(len(original_waveform)), original_waveform)
            smooth_amplitude = cs(smooth_time)

            # Find highest peaks separated by at least n data points in the smoothed curve
            n = 15
            peaks, _ = find_peaks(smooth_amplitude, distance=n)
            troughs, _ = find_peaks(-smooth_amplitude, distance=n)
            highest_peaks = peaks[np.argsort(smooth_amplitude[peaks])[-5:]]
            highest_peaks = np.sort(highest_peaks)
            relevant_troughs = np.array([])
            for p in range(len(highest_peaks)):
                c = 0
                for t in troughs:
                    if t > highest_peaks[p]:
                        if p != 4:
                            if t < highest_peaks[p+1]:
                                relevant_troughs = np.append(relevant_troughs, int(t))
                                break
                        else:
                            relevant_troughs = np.append(relevant_troughs, int(t))
                            break
            relevant_troughs = relevant_troughs.astype('i')

            # Plot the original ABR waveform
            fig.add_trace(go.Scatter(x=np.linspace(0, 10, len(original_waveform)), y=original_waveform, mode='lines', name='Original ABR', opacity=0.8))

            # Plot the cubic spline interpolation
            fig.add_trace(go.Scatter(x=np.linspace(0,10,len(smooth_time)), y=smooth_amplitude, mode='lines', name='Cubic Spline Interpolation'))

            # Mark the highest peaks with red markers
            fig.add_trace(go.Scatter(x=np.linspace(0,10,len(smooth_time))[highest_peaks], y=smooth_amplitude[highest_peaks], mode='markers', marker=dict(color='red'), name='Peaks'))

            # Mark the relevant troughs with blue markers
            fig.add_trace(go.Scatter(x=np.linspace(0,10,len(smooth_time))[relevant_troughs], y=smooth_amplitude[relevant_troughs], mode='markers', marker=dict(color='blue'), name='Troughs'))

            # Set layout options
            fig.update_layout(title=f'{uploaded_files[i].name}', xaxis_title='Time (ms)', yaxis_title='Voltage (mV)', legend=dict(x=0, y=1, traceorder='normal'))
            i+=1

    # Show the plot using Streamlit
    return fig

def update_title_and_legend_if_single_frequency(fig, selected_freqs):
    if len(set(selected_freqs)) == 1:
        fig.update_layout(title=f'{uploaded_file.name} - Freq: {selected_freqs[0]} Hz')
        for trace in fig.data:
            if 'Freq' in trace.name:
                trace.name = trace.name.replace(f'Freq: {trace.name.split(" ")[1]} Hz, ', '')
    return fig

def plot_waves_single_frequency(df, freq, y_min, y_max, plot_time_warped=False):
    if level:
        db_column = 'Level(dB)'
    else:
        db_column = 'PostAtten(dB)'

    if len(selected_dfs) == 0:
        st.write("No files selected.")
        return

    for idx, file_df in enumerate(selected_dfs):
        fig = go.Figure()

        # Filter DataFrame to include only data for the specified frequency
        df_filtered = file_df[file_df['Freq(Hz)'] == freq]

        # Get unique dB levels for the filtered DataFrame
        db_levels = sorted(df_filtered[db_column].unique())

        if plot_time_warped:
            original_waves = []  # Only store original waves if not plotting time warped

        for i, db in enumerate(db_levels):
            khz = df_filtered[df_filtered[db_column] == db]
            
            if not khz.empty:
                index = khz.index.values[0]
                final = df_filtered.loc[index, '0':]
                final = pd.to_numeric(final, errors='coerce')

                if multiply_y_factor != 1:
                    y_values = final * multiply_y_factor
                else:
                    y_values = final

                if plot_time_warped:
                    original_waves.append(y_values.to_list()) 
                else:
                    # Define color scale from dark red to light red based on dB level
                    col_diff = np.linspace(255, 125, len(db_levels))
                    color_scale = f'rgb(0, {col_diff[i]}, {col_diff[i]})'  # Adjust color intensity for each dB level
                    fig.add_trace(go.Scatter(x=np.linspace(0,10, len(y_values)), y=y_values, mode='lines', name=f'db: {db} dB', line=dict(color=color_scale)))

        if plot_time_warped:
            # Convert original waves to a 2D numpy array
            original_waves_array = np.array([wave[:-1] for wave in original_waves])

            try:
                # Apply time warping to all waves in the array
                time = np.linspace(0, 10, original_waves_array.shape[1])
                obj = fs.fdawarp(original_waves_array.T, time)
                obj.srsf_align(parallel=True)
                warped_waves_array = obj.fn.T  # Use the time-warped curves
                
                # Plot time-warped curves
                for i, db in enumerate(db_levels):
                    col_diff = np.linspace(255, 125, len(db_levels))
                    color_scale = f'rgb(0, {col_diff[i]}, {col_diff[i]})'  # Adjust color intensity for each dB level
                    fig.add_trace(go.Scatter(x=np.linspace(0,10, len(warped_waves_array[i])), y=warped_waves_array[i], mode='lines', name=f'dB: {db} dB', line=dict(color=color_scale)))

            except IndexError:
                pass

        fig.update_layout(title=f'{selected_files[idx].split("/")[-1]} - Frequency: {freq} Hz', xaxis_title='Time (ms)', yaxis_title='Voltage (mV)')
        fig.update_layout(annotations=annotations)
        fig.update_layout(yaxis_range=[y_min, y_max])
        custom_width = 700
        custom_height = 450

        fig.update_layout(width=custom_width, height=custom_height)

        st.plotly_chart(fig)

def plot_waves_single_db(df, db, y_min, y_max):
    fig = go.Figure()

    if level:
        d = 'Level(dB)'
    else:
        d = 'PostAtten(dB)'
    
    if len(selected_dfs) > 1:
        st.write("Can only process one file at a time.")
        return
    else:
        df = selected_dfs[0]

    for freq in sorted(df['Freq(Hz)'].unique()):
        khz = df[(df['Freq(Hz)'] == freq) & (df[d] == db)]
        
        if not khz.empty:
            index = khz.index.values[0]
            final = df.loc[index, '0':]
            final = pd.to_numeric(final, errors='coerce')

            if multiply_y_factor != 1:
                y_values = final * multiply_y_factor
            else:
                y_values = final

            fig.add_trace(go.Scatter(x=np.linspace(0,10, len(y_values)), y=y_values, mode='lines', name=f'Frequency: {freq} Hz'))
            
    fig.update_layout(width=700, height=450)
    fig.update_layout(title=f'{selected_files[0].split("/")[-1]} - dB Level: {db}', xaxis_title='Index', yaxis_title='Voltage (mV)')
    fig.update_layout(annotations=annotations)
    fig.update_layout(yaxis_range=[y_min, y_max])

    return fig

def plot_waves_single_tuple(df, freq, db, y_min, y_max):
    fig = go.Figure()
    i=0
    if level:
        d = 'Level(dB)'
    else:
        d = 'PostAtten(dB)'
    
    for df in selected_dfs:
        khz = df[(df['Freq(Hz)'] == freq) & (df[d] == db)]
        
        if not khz.empty:
            index = khz.index.values[0]
            final = df.loc[index, '0':].dropna()
            final = pd.to_numeric(final, errors='coerce')[:-1]

            time_axis = np.linspace(0, 10, len(final))

            # Find highest peaks separated by at least n data points

            if multiply_y_factor != 1:
                y_values = final * multiply_y_factor
            else:
                y_values = final
            
            # Apply Gaussian smoothing to the original ABR waveform
            smoothed_waveform = gaussian_filter1d(y_values, sigma=1.8125)

            # Find highest peaks separated by at least n data points in the smoothed curve
            n = 20
            # Find highest peaks separated by at least n data points in the smoothed curve
            smoothed_peaks, _ = find_peaks(smoothed_waveform[26:], distance=n)
            smoothed_troughs, _ = find_peaks(-smoothed_waveform, distance=12)
            sorted_indices = np.argsort(smoothed_waveform[smoothed_peaks+26])
            # Get the indices of the highest peaks (top 5 in this case)
            highest_smoothed_peaks = smoothed_peaks[sorted_indices[-5:]] + 26
            relevant_troughs = np.array([])
            for p in range(len(highest_smoothed_peaks)):
                c = 0
                for t in smoothed_troughs:
                    if t > highest_smoothed_peaks[p]:
                        if p != 4:
                            try:
                                if t < highest_smoothed_peaks[p+1]:
                                    relevant_troughs = np.append(relevant_troughs, int(t))
                                    break
                            except IndexError:
                                pass
                        else:
                            relevant_troughs = np.append(relevant_troughs, int(t))
                            break
            relevant_troughs = relevant_troughs.astype('i')

            fig.add_trace(go.Scatter(x=np.linspace(0,10, len(y_values)), y=y_values, mode='lines', name=f'{selected_files[i].split("/")[-1]}'))

            # Mark the highest peaks with red markers
            fig.add_trace(go.Scatter(x=np.linspace(0,10,len(y_values))[highest_smoothed_peaks], y=y_values[highest_smoothed_peaks], mode='markers', marker=dict(color='red'), name='Peaks'))

            # Mark the relevant troughs with blue markers
            fig.add_trace(go.Scatter(x=np.linspace(0,10,len(y_values))[relevant_troughs], y=y_values[relevant_troughs], mode='markers', marker=dict(color='blue'), name='Troughs'))

            i+=1

    fig.update_layout(width=700, height=450)
    fig.update_layout(title=f'Freq = {freq}, dB = {db}', xaxis_title='Time (ms)', yaxis_title='Voltage (mV)')
    fig.update_layout(annotations=annotations)
    fig.update_layout(yaxis_range=[y_min, y_max])

    return fig

def plotting_waves_gauss(df, freq, db, n=15, sigma=3):
    fig = go.Figure()

    if level:
        d = 'Level(dB)'
    else:
        d = 'PostAtten(dB)'

    for df in selected_dfs:
        khz = df[df['Freq(Hz)'] == freq]
        dbkhz = khz[khz[d] == db]
        if not dbkhz.empty:
            index = dbkhz.index.values[0]
            original_waveform = df.loc[index, '0':]
            original_waveform = pd.to_numeric(original_waveform, errors='coerce')

            # Apply Gaussian smoothing to the original ABR waveform
            smoothed_waveform = gaussian_filter1d(original_waveform, sigma=sigma)

            # Find highest peaks separated by at least n data points in the original curve
            original_peaks, _ = find_peaks(original_waveform, distance=n)
            highest_original_peaks = original_peaks[np.argsort(original_waveform[original_peaks])[-5:]]

            # Find highest peaks separated by at least n data points in the smoothed curve
            smoothed_peaks, _ = find_peaks(smoothed_waveform, distance=n)
            highest_smoothed_peaks = smoothed_peaks[np.argsort(smoothed_waveform[smoothed_peaks])[-5:]]

            # Plot the original ABR waveform
            fig.add_trace(go.Scatter(x=np.arange(len(original_waveform)), y=original_waveform, mode='lines', name='Original ABR'))

            # Plot the smoothed ABR waveform
            fig.add_trace(go.Scatter(x=np.arange(len(smoothed_waveform)), y=smoothed_waveform, mode='lines', name=f'Gaussian Smoothed (sigma={sigma})'))

            if highest_original_peaks.size > 0:  # Check if highest_original_peaks is not empty
                first_original_peak = np.sort(highest_original_peaks)[0]
                fig.add_trace(go.Scatter(x=[first_original_peak], y=[original_waveform[first_original_peak]], mode='markers', marker=dict(color='red'), name='Original Peaks'))

            if highest_smoothed_peaks.size > 0:  # Check if highest_smoothed_peaks is not empty
                first_smoothed_peak = np.sort(highest_smoothed_peaks)[0]
                fig.add_trace(go.Scatter(x=[first_smoothed_peak], y=[smoothed_waveform[first_smoothed_peak]], mode='markers', marker=dict(color='blue'), name='Smoothed Peaks'))

    #fig.update_layout(title=f'Sheet: {filename}', xaxis_title='Index', yaxis_title='Voltage (mV)', legend=dict(x=0, y=1, traceorder='normal'))

    return fig

def plot_3d_surface(df, freq, y_min, y_max):
    if level:
        db_column = 'Level(dB)'
    else:
        db_column = 'PostAtten(dB)'

    if len(selected_dfs) == 0:
        st.write("No files selected.")
        return
    
    for idx, file_df in enumerate(selected_dfs):
        fig = go.Figure()

        # Filter DataFrame to include only data for the specified frequency
        df_filtered = file_df[file_df['Freq(Hz)'] == freq]

        # Get unique dB levels for the filtered DataFrame
        db_levels = sorted(df_filtered[db_column].unique())

        original_waves = []  # List to store original waves
        wave_colors = [f'rgb(255, 0, 255)' for b in np.linspace(0, 0, len(db_levels))]
        connecting_line_color = 'rgba(0, 255, 0, 0.3)'

        for db in db_levels:
            khz = df_filtered[df_filtered[db_column] == db]
            
            if not khz.empty:
                index = khz.index.values[0]
                final = df_filtered.loc[index, '0':]
                final = pd.to_numeric(final, errors='coerce')

                if multiply_y_factor != 1:
                    y_values = final * multiply_y_factor
                else:
                    y_values = final

                original_waves.append(y_values.to_list()) 

        # Convert original waves to a 2D numpy array
        original_waves_array = np.array([wave[:-1] for wave in original_waves])

        try:
            # Apply time warping to all waves in the array
            time = np.linspace(0, 10, original_waves_array.shape[1])
            obj = fs.fdawarp(original_waves_array.T, time)
            obj.srsf_align(parallel=True)
            warped_waves_array = obj.fn.T  # Use the time-warped curves
        except IndexError:
            pass

        # Plot all time-warped waves in the array
        for i, (db, warped_waves) in enumerate(zip(db_levels, warped_waves_array)):
            fig.add_trace(go.Scatter3d(x=[db] * len(warped_waves), y=np.linspace(0, 10, len(warped_waves)), z=warped_waves, mode='lines', name=f'dB: {db}', line=dict(color=wave_colors[i])))

        # Create surface connecting the curves at each time point
        for i in range(len(time)):
            z_values_at_time = [warped_waves_array[j, i] for j in range(len(db_levels))]
            fig.add_trace(go.Scatter3d(x=db_levels, y=[time[i]] * len(db_levels), z=z_values_at_time, mode='lines', name=f'Time: {time[i]:.2f} ms', line=dict(color=connecting_line_color)))

        fig.update_layout(width=700, height=450)
        fig.update_layout(title=f'{selected_files[idx].split("/")[-1]} - Frequency: {freq} Hz', scene=dict(xaxis_title=f'dB {is_level}', yaxis_title='Time (ms)', zaxis_title='Voltage (mV)'))
        fig.update_layout(annotations=annotations)
        fig.update_layout(scene=dict(zaxis=dict(range=[y_min, y_max])))

        khz = file_df[(file_df['Freq(Hz)'] == freq)]
        if not khz.empty:
            st.plotly_chart(fig)

def display_metrics_table(df, freq, db, baseline_level):
    if level:
        d = 'Level(dB)'
    else:
        d = 'PostAtten(dB)'

    khz = df[(df['Freq(Hz)'] == freq) & (df[d] == db)]
    if not khz.empty:
        index = khz.index.values[0]
        final = df.loc[index, '0':]
        final = pd.to_numeric(final, errors='coerce')

        if multiply_y_factor != 1:
            y_values = final * multiply_y_factor
        else:
            y_values = final
        
        # Adjust the waveform by subtracting the baseline level
        y_values -= baseline_level

        # Find highest peaks separated by at least n data points
        peaks, _ = find_peaks(y_values, distance=15)
        troughs, _ = find_peaks(-y_values, distance=15)
        highest_peaks = peaks[np.argsort(final[peaks])[-5:]]
        highest_peaks = np.sort(highest_peaks)
        relevant_troughs = np.array([])
        for p in range(len(highest_peaks)):
            c = 0
            for t in troughs:
                if t > highest_peaks[p]:
                    if p != 4:
                        if t < highest_peaks[p+1]:
                            relevant_troughs = np.append(relevant_troughs, int(t))
                            break
                    else:
                        relevant_troughs = np.append(relevant_troughs, int(t))
                        break
        relevant_troughs = relevant_troughs.astype('i')

        if highest_peaks.size > 0:  # Check if highest_peaks is not empty
            first_peak_amplitude = y_values[highest_peaks[0]] - y_values[relevant_troughs[0]]
            latency_to_first_peak = highest_peaks[0] * (10 / len(y_values))  # Assuming 10 ms duration for waveform

            if len(highest_peaks) >= 4:
                amplitude_ratio = (y_values[highest_peaks[0]] - y_values[relevant_troughs[0]]) / (y_values[highest_peaks[3]] - y_values[relevant_troughs[3]])
            else:
                amplitude_ratio = np.nan

            metrics_table = pd.DataFrame({
                'Metric': ['First Peak Amplitude (mV)', 'Latency to First Peak (ms)', 'Amplitude Ratio (Peak1/Peak4)', 'Estimated Threshold'],
                'Value': [first_peak_amplitude, latency_to_first_peak, amplitude_ratio, calculate_hearing_threshold(df, freq)],
            })
            #st.table(metrics_table)
        return metrics_table

def display_metrics_table_all_db(selected_dfs, freq, db_levels, baseline_level, level=True, multiply_y_factor=1):
    if level:
        db_column = 'Level(dB)'
    else:
        db_column = 'PostAtten(dB)'
        
    metrics_data = {'File Name': [], 'Frequency (Hz)': [], 'dB Level': [], 'First Peak Amplitude (mV)': [], 'Latency to First Peak (ms)': [], 'Amplitude Ratio (Peak1/Peak4)': []}

    for file_df, file_name in zip(selected_dfs, selected_files):
        for db in db_levels:
            khz = file_df[(file_df['Freq(Hz)'] == freq) & (file_df[db_column] == db)]
            if not khz.empty:
                index = khz.index.values[0]
                final = file_df.loc[index, '0':]
                final = pd.to_numeric(final, errors='coerce')

                if multiply_y_factor != 1:
                    y_values = final * multiply_y_factor
                else:
                    y_values = final

                # Adjust the waveform by subtracting the baseline level
                y_values -= baseline_level

                # Find highest peaks separated by at least n data points
                peaks, _ = find_peaks(y_values, distance=int((15 / 243) * len(y_values)))
                troughs, _ = find_peaks(-y_values, distance=int((15 / 243) * len(y_values)))
                highest_peaks = peaks[np.argsort(final[peaks])[-5:]]
                highest_peaks = np.sort(highest_peaks)
                relevant_troughs = np.array([])
                for p in range(len(highest_peaks)):
                    c = 0
                    for t in troughs:
                        if t > highest_peaks[p]:
                            if p != 4:
                                if t < highest_peaks[p + 1]:
                                    relevant_troughs = np.append(relevant_troughs, int(t))
                                    break
                            else:
                                relevant_troughs = np.append(relevant_troughs, int(t))
                                break
                relevant_troughs = relevant_troughs.astype('i')

                if highest_peaks.size > 0:  # Check if highest_peaks is not empty
                    first_peak_amplitude = y_values[highest_peaks[0]] - y_values[relevant_troughs[0]]
                    latency_to_first_peak = highest_peaks[0] * (10 / len(y_values))  # Assuming 10 ms duration for waveform

                    if len(highest_peaks) >= 4 and len(relevant_troughs) >= 4:
                        amplitude_ratio = (y_values[highest_peaks[0]] - y_values[relevant_troughs[0]]) / (
                                    y_values[highest_peaks[3]] - y_values[relevant_troughs[3]])
                    else:
                        amplitude_ratio = np.nan

                    metrics_data['File Name'].append(file_name.split("/")[-1])
                    metrics_data['Frequency (Hz)'].append(freq)
                    metrics_data['dB Level'].append(db)
                    metrics_data['First Peak Amplitude (mV)'].append(first_peak_amplitude)
                    metrics_data['Latency to First Peak (ms)'].append(latency_to_first_peak)
                    metrics_data['Amplitude Ratio (Peak1/Peak4)'].append(amplitude_ratio)

    metrics_table = pd.DataFrame(metrics_data)
    st.table(metrics_table)

def plot_waves_stacked(df, freq, y_min, y_max, plot_time_warped=False):
    if level:
        db_column = 'Level(dB)'
    else:
        db_column = 'PostAtten(dB)'

    if len(selected_dfs) == 0:
        st.write("No files selected.")
        return

    for idx, file_df in enumerate(selected_dfs):
        fig = go.Figure()

        # Get unique dB levels
        unique_dbs = sorted(file_df[db_column].unique())

        # Calculate the vertical offset for each waveform
        num_dbs = len(unique_dbs)
        vertical_spacing = 25 / num_dbs

        # Initialize an offset for each dB level
        db_offsets = {db: y_min + i * vertical_spacing for i, db in enumerate(unique_dbs)}

        # Find the highest dB level
        max_db = max(unique_dbs)

        # Process and plot each waveform
        for db in sorted(file_df[db_column].unique(), reverse=True):
            khz = file_df[(file_df['Freq(Hz)'] == freq) & (file_df[db_column] == db)]

            if not khz.empty:
                index = khz.index.values[0]
                final = file_df.loc[index, '0':]
                final = pd.to_numeric(final, errors='coerce')[:-1]

                # Normalize the waveform
                if db == max_db:
                    max_value = final.abs().max()  # Find the maximum absolute value
                final_normalized = final / max_value  # Normalize

                # Scale relative to the highest decibel wave
                #final_scaled = final_normalized * (db / max_db)

                # Apply the vertical offset
                y_values = final_normalized + db_offsets[db]

                # Optionally apply time warping
                if plot_time_warped:
                    # ... (your time warping code here)
                    pass

                # Plot the waveform
                fig.add_trace(go.Scatter(x=np.linspace(0, 10, y_values.shape[0]),
                                        y=y_values,
                                        mode='lines',
                                        name=f'dB: {db}',
                                        #line=dict(color='black')
                                        ))

        fig.update_layout(title=f'{selected_files[idx].split("/")[-1]} - Frequency: {freq} Hz',
                        xaxis_title='Time (ms)',
                        yaxis_title='Voltage (mV)')
        fig.update_layout(yaxis_range=[y_min, y_max])
        # Set custom width and height (in pixels)
        custom_width = 400
        custom_height = 700

        fig.update_layout(width=custom_width, height=custom_height)

        fig.update_layout(yaxis=dict(showticklabels=False, showgrid=False, zeroline=False))
        fig.update_layout(xaxis=dict(showgrid=False, zeroline=False))

        khz = file_df[(file_df['Freq(Hz)'] == freq)]
        if not khz.empty:
            st.plotly_chart(fig)

def arfread(PATH, **kwargs):
    # defaults
    PLOT = kwargs.get('PLOT', False)
    RP = kwargs.get('RP', False)
    
    isRZ = not RP
    
    data = {'RecHead': {}, 'groups': []}

    # open file
    with open(PATH, 'rb') as fid:
        # open RecHead data
        data['RecHead']['ftype'] = struct.unpack('h', fid.read(2))[0]
        data['RecHead']['ngrps'] = struct.unpack('h', fid.read(2))[0]
        data['RecHead']['nrecs'] = struct.unpack('h', fid.read(2))[0]
        data['RecHead']['grpseek'] = struct.unpack('200i', fid.read(4*200))
        data['RecHead']['recseek'] = struct.unpack('2000i', fid.read(4*2000))
        data['RecHead']['file_ptr'] = struct.unpack('i', fid.read(4))[0]

        data['groups'] = []
        bFirstPass = True
        for x in range(data['RecHead']['ngrps']):
            # jump to the group location in the file
            fid.seek(data['RecHead']['grpseek'][x], 0)

            # open the group
            data['groups'].append({
                'grpn': struct.unpack('h', fid.read(2))[0],
                'frecn': struct.unpack('h', fid.read(2))[0],
                'nrecs': struct.unpack('h', fid.read(2))[0],
                'ID': get_str(fid.read(16)),
                'ref1': get_str(fid.read(16)),
                'ref2': get_str(fid.read(16)),
                'memo': get_str(fid.read(50)),
            })

            # read temporary timestamp
            if bFirstPass:
                if isRZ:
                    ttt = struct.unpack('q', fid.read(8))[0]
                    fid.seek(-8, 1)
                    data['fileType'] = 'BioSigRZ'
                else:
                    ttt = struct.unpack('I', fid.read(4))[0]
                    fid.seek(-4, 1)
                    data['fileType'] = 'BioSigRP'
                data['fileTime'] = datetime.datetime.utcfromtimestamp(ttt/86400 + datetime.datetime(1970, 1, 1).timestamp()).strftime('%Y-%m-%d %H:%M:%S')
                bFirstPass = False

            if isRZ:
                grp_t_format = 'q'
                beg_t_format = 'q'
                end_t_format = 'q'
                read_size = 8
            else:
                grp_t_format = 'I'
                beg_t_format = 'I'
                end_t_format = 'I'
                read_size = 4

            data['groups'][x]['beg_t'] = struct.unpack(beg_t_format, fid.read(read_size))[0]
            data['groups'][x]['end_t'] = struct.unpack(end_t_format, fid.read(read_size))[0]

            data['groups'][x].update({
                'sgfname1': get_str(fid.read(100)),
                'sgfname2': get_str(fid.read(100)),
                'VarName1': get_str(fid.read(15)),
                'VarName2': get_str(fid.read(15)),
                'VarName3': get_str(fid.read(15)),
                'VarName4': get_str(fid.read(15)),
                'VarName5': get_str(fid.read(15)),
                'VarName6': get_str(fid.read(15)),
                'VarName7': get_str(fid.read(15)),
                'VarName8': get_str(fid.read(15)),
                'VarName9': get_str(fid.read(15)),
                'VarName10': get_str(fid.read(15)),
                'VarUnit1': get_str(fid.read(5)),
                'VarUnit2': get_str(fid.read(5)),
                'VarUnit3': get_str(fid.read(5)),
                'VarUnit4': get_str(fid.read(5)),
                'VarUnit5': get_str(fid.read(5)),
                'VarUnit6': get_str(fid.read(5)),
                'VarUnit7': get_str(fid.read(5)),
                'VarUnit8': get_str(fid.read(5)),
                'VarUnit9': get_str(fid.read(5)),
                'VarUnit10': get_str(fid.read(5)),
                'SampPer_us': struct.unpack('f', fid.read(4))[0],
                'cc_t': struct.unpack('i', fid.read(4))[0],
                'version': struct.unpack('h', fid.read(2))[0],
                'postproc': struct.unpack('i', fid.read(4))[0],
                'dump': get_str(fid.read(92)),
                'recs': [],
            })

            for i in range(data['groups'][x]['nrecs']):
                record_data = {
                        'recn': struct.unpack('h', fid.read(2))[0],
                        'grpid': struct.unpack('h', fid.read(2))[0],
                        'grp_t': struct.unpack(grp_t_format, fid.read(read_size))[0],
                        #'grp_d': datetime.utcfromtimestamp(data['groups'][x]['recs'][i]['grp_t']/86400 + datetime(1970, 1, 1).timestamp()).strftime('%Y-%m-%d %H:%M:%S'),
                        'newgrp': struct.unpack('h', fid.read(2))[0],
                        'sgi': struct.unpack('h', fid.read(2))[0],
                        'chan': struct.unpack('B', fid.read(1))[0],
                        'rtype': get_str(fid.read(1)),
                        'npts': struct.unpack('H' if isRZ else 'h', fid.read(2))[0],
                        'osdel': struct.unpack('f', fid.read(4))[0],
                        'dur_ms': struct.unpack('f', fid.read(4))[0],
                        'SampPer_us': struct.unpack('f', fid.read(4))[0],
                        'artthresh': struct.unpack('f', fid.read(4))[0],
                        'gain': struct.unpack('f', fid.read(4))[0],
                        'accouple': struct.unpack('h', fid.read(2))[0],
                        'navgs': struct.unpack('h', fid.read(2))[0],
                        'narts': struct.unpack('h', fid.read(2))[0],
                        'beg_t': struct.unpack(beg_t_format, fid.read(read_size))[0],
                        'end_t': struct.unpack(end_t_format, fid.read(read_size))[0],
                        'Var1': struct.unpack('f', fid.read(4))[0],
                        'Var2': struct.unpack('f', fid.read(4))[0],
                        'Var3': struct.unpack('f', fid.read(4))[0],
                        'Var4': struct.unpack('f', fid.read(4))[0],
                        'Var5': struct.unpack('f', fid.read(4))[0],
                        'Var6': struct.unpack('f', fid.read(4))[0],
                        'Var7': struct.unpack('f', fid.read(4))[0],
                        'Var8': struct.unpack('f', fid.read(4))[0],
                        'Var9': struct.unpack('f', fid.read(4))[0],
                        'Var10': struct.unpack('f', fid.read(4))[0],
                        'data': [] #list(struct.unpack(f'{data["groups"][x]["recs"][i]["npts"]}f', fid.read(4*data['groups'][x]['recs'][i]['npts'])))
                    }
                
                # skip all 10 cursors placeholders
                fid.seek(36*10, 1)
                record_data['data'] = list(struct.unpack(f'{record_data["npts"]}f', fid.read(4*record_data['npts'])))

                record_data['grp_d'] = datetime.datetime.utcfromtimestamp(record_data['grp_t'] / 86400 + datetime.datetime(1970, 1, 1).timestamp()).strftime('%Y-%m-%d %H:%M:%S')

                data['groups'][x]['recs'].append(record_data)

            if PLOT:
                import matplotlib.pyplot as plt

                # determine reasonable spacing between plots
                d = [x['data'] for x in data['groups'][x]['recs']]
                plot_offset = max(max(map(abs, [item for sublist in d for item in sublist]))) * 1.2

                plt.figure()

                for i in range(data['groups'][x]['nrecs']):
                    plt.plot([item - plot_offset * i for item in data['groups'][x]['recs'][i]['data']])
                    plt.hold(True)

                plt.title(f'Group {data["groups"][x]["grpn"]}')
                plt.axis('off')
                plt.show()

    return data

def get_str(data):
    # return string up until null character only
    ind = data.find(b'\x00')
    if ind > 0:
        data = data[:ind]
    return data.decode('utf-8')

def calculate_hearing_threshold(df, freq):
    db_values = []
    
    waves_array = []  # Array to store all waves

    for db in range(0,95,5):
        khz = df[(df['Freq(Hz)'] == freq) & (df['Level(dB)'] == db)]
        
        if not khz.empty:
            index = khz.index.values[0]
            final = df.loc[index, '0':].dropna()
            final = pd.to_numeric(final, errors='coerce')[:-1]

            if multiply_y_factor != 1:
                y_values = final * multiply_y_factor
            else:
                y_values = final
            db_values.append(db)

            waves_array.append(y_values.to_list())

    # Filter waves and dB values for the specified frequency
    waves_fd = FDataGrid(waves_array)
    fpca_discretized = FPCA(n_components=2)
    fpca_discretized.fit(waves_fd)
    projection = fpca_discretized.transform(waves_fd)

    nearest_neighbors = NearestNeighbors(n_neighbors=2)
    neighbors = nearest_neighbors.fit(projection[:, :2])
    distances, indices = neighbors.kneighbors(projection[:, :2])
    distances = np.sort(distances, axis=0)
    distances = distances[:,1]

    knee_locator = KneeLocator(range(len(distances)), distances, curve='convex', direction='increasing')
    eps = distances[knee_locator.knee]

    # Apply DBSCAN clustering
    dbscan = DBSCAN(eps=eps)
    clusters = dbscan.fit_predict(projection[:, :2])

    # Create DataFrame with projection results and cluster labels
    df = pd.DataFrame(projection[:, :2], columns=['1st_PC', '2nd_PC'])
    df['Cluster'] = clusters
    print(clusters)
    df['DB_Value'] = db_values

    # Find the minimum hearing threshold value among the outliers
    min_threshold = np.min(df[df['Cluster']==-1]['DB_Value'])

    return min_threshold

# Streamlit UI
st.title("Wave Plotting App")
st.sidebar.header("Upload File")
uploaded_files = st.sidebar.file_uploader("Choose a file", type=["csv", "arf"], accept_multiple_files=True)
is_rz_file = st.sidebar.radio("Select ARF File Type:", ("RP", "RZ"))
is_level = st.sidebar.radio("Select dB You Are Studying:", ("Attenuation", "Level"))

annotations = []


if uploaded_files:
    dfs = []
    selected_files = []
    selected_dfs = []
    
    for idx, file in enumerate(uploaded_files):
        # Use tempfile
        temp_file_path = os.path.join(tempfile.gettempdir(), file.name)
        with open(temp_file_path, 'wb') as temp_file:
            temp_file.write(file.read())
        #st.sidebar.markdown(f"**File Name:** {file.name}")
        selected = st.sidebar.checkbox(f"{file.name}", key=f"file_{idx}")
        
        if selected:
            selected_files.append(temp_file_path)

        if file.name.endswith(".arf"):
        # Read ARF file
            if is_rz_file == 'RP':
                data = arfread(temp_file.name, RP=True) 
            else:
                data = arfread(temp_file.name) 
            
            # Process ARF data
            rows = []
            freqs = []
            dbs = []

            for group in data['groups']:
                for rec in group['recs']:
                    # Extract data
                    freq = rec['Var1']
                    db = rec['Var2']
                    
                    # Construct row  
                    wave_cols = list(enumerate(rec['data']))
                    wave_data = {f'{i}':v*1e6 for i, v in wave_cols} 
                    
                    if is_level == 'Level':
                        row = {'Freq(Hz)': freq, 'Level(dB)': db, **wave_data}
                        rows.append(row)
                    if is_level == 'Attenuation':
                        row = {'Freq(Hz)': freq, 'PostAtten(dB)': db, **wave_data}
                        rows.append(row)

            df = pd.DataFrame(rows)

        elif file.name.endswith(".csv"):
            # Process CSV
            if pd.read_csv(temp_file_path).shape[1] > 1:
                df = pd.read_csv(temp_file_path)
            else:
                df = pd.read_csv(temp_file_path, skiprows=2)
            
        # Append df to list
        dfs.append(df)
        if temp_file_path in selected_files:
            selected_dfs.append(df)

    level = (is_level == 'Level')

    # Get distinct frequency and dB level values across all files
    distinct_freqs = sorted(pd.concat([df['Freq(Hz)'] for df in dfs]).unique())
    distinct_dbs = sorted(pd.concat([df['Level(dB)'] if level else df['PostAtten(dB)'] for df in dfs]).unique())
    
    multiply_y_factor = st.sidebar.number_input("Multiply Y Values by Factor", value=1.0)

    # Frequency dropdown options
    freq = st.sidebar.selectbox("Select Frequency (Hz)", options=distinct_freqs, index=0)

    # dB Level dropdown options
    db = st.sidebar.selectbox(f'Select dB {is_level}', options=distinct_dbs, index=0)

    y_min = st.sidebar.number_input("Y-axis Minimum", value=-5.0)
    y_max = st.sidebar.number_input("Y-axis Maximum", value=5.0)

    baseline_level_str = st.sidebar.text_input("Set Baseline Level", "0.0")
    baseline_level = float(baseline_level_str)

    plot_time_warped = st.sidebar.checkbox("Plot Time Warped Curves", False)

    # Create a plotly figure
    fig = go.Figure()

    #scatter_plot_option = st.sidebar.checkbox("Plot Waves as Scatter Plot", False)

    if st.sidebar.button("Plot Waves at Single Frequency"):
        if plot_time_warped:
            fig = plot_waves_single_frequency(df, freq, y_min, y_max, plot_time_warped=True)
        else:
            fig = plot_waves_single_frequency(df, freq, y_min, y_max, plot_time_warped=False)
        display_metrics_table_all_db(selected_dfs, freq, distinct_dbs, baseline_level)

    if st.sidebar.button("Plot Waves at Single dB Level"):
        fig = plot_waves_single_db(df, db, y_min, y_max)
        st.plotly_chart(fig)
        display_metrics_table(df, freq, db, baseline_level)

    if st.sidebar.button("Plot Waves at Single Tuple (Frequency, dB)"):
        fig = plot_waves_single_tuple(df, freq, db, y_min, y_max)
        st.plotly_chart(fig)
        metrics_df = display_metrics_table(df, freq, db, baseline_level)
        if metrics_df is not None:
            st.table(metrics_df)
        if st.button("Download metrics"):
            csv = metrics_df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()  # Some strings
            link = f'<a href="data:file/csv;base64,{b64}" download="metrics_table.csv">Download Metrics Table CSV</a>'
            st.markdown(link, unsafe_allow_html=True)

    
    if st.sidebar.button("Plot Stacked Waves at Single Frequency"):
        if plot_time_warped:
            plot_waves_stacked(df, freq, y_min, y_max, plot_time_warped=True)
        else:
            plot_waves_stacked(df, freq, y_min, y_max, plot_time_warped=False)
    
    #if st.sidebar.button("Plot Waves with Cubic Spline"):
    #    fig = plotting_waves_cubic_spline(df, freq, db)
    #    fig.update_layout(yaxis_range=[y_min, y_max])
    #    st.plotly_chart(fig)

    if st.sidebar.button("Plot 3D Surface"):
        plot_3d_surface(df, freq, y_min, y_max)
    
    #if st.sidebar.button("Plot Waves with Gaussian Smoothing"):
    #    fig_gauss = plotting_waves_gauss(dfs, freq, db)
    #    st.plotly_chart(fig_gauss)
    
    #st.markdown(get_download_link(fig), unsafe_allow_html=True)
