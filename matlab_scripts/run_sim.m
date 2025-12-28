% MATLAB simulation entrypoint for thermal analysis
% 
% Expected workspace variables:
%   geometry_file - Path to STEP/STL geometry file
%   output_dir    - Directory for results
%   plots_dir     - Directory for plots
%   ambientC      - Ambient temperature (°C)
%   heatW         - Heat source power (W)
%   hConv         - Convection coefficient (W/m²·K)
%
% Outputs to workspace:
%   max_tempC     - Maximum temperature (°C)
%   mass_g        - Mass (grams, if material density known)

%% Setup
fprintf('Starting thermal simulation...\n');
fprintf('Geometry: %s\n', geometry_file);

%% Create PDE model
model = createpde('thermal', 'steadystate');

%% Import geometry
try
    importGeometry(model, geometry_file);
    fprintf('Geometry imported successfully\n');
catch ME
    fprintf('Error importing geometry: %s\n', ME.message);
    error('Failed to import geometry');
end

%% Material properties (example: aluminum)
k_thermal = 205;  % W/(m·K) - thermal conductivity
rho = 2700;       % kg/m³ - density
cp = 900;         % J/(kg·K) - specific heat

thermalProperties(model, 'ThermalConductivity', k_thermal, ...
                        'MassDensity', rho, ...
                        'SpecificHeat', cp);

%% Boundary conditions
% Find external faces (could be improved with better face detection)
% For now, assume all external faces have convection

% Apply convection to all faces (simplified)
thermalBC(model, 'Face', 1:model.Geometry.NumFaces, ...
         'ConvectionCoefficient', hConv, ...
         'AmbientTemperature', ambientC);

%% Heat source
% Apply heat source to a specific region (example: center of geometry)
% This is simplified - in practice, you'd identify the heat source location

% For demonstration, apply internal heat generation if geometry has a volume
if model.Geometry.NumCells > 0
    % Apply heat generation to first cell (simplified)
    % Total heat / volume
    bbox = model.Geometry.BoundingBox;
    approx_volume = prod(bbox(:,2) - bbox(:,1));  % m³
    heat_gen = heatW / approx_volume;  % W/m³
    
    internalHeatSource(model, heat_gen);
    fprintf('Heat source: %.2f W distributed over %.4f m³\n', heatW, approx_volume);
end

%% Mesh
generateMesh(model, 'Hmax', 0.01);  % 10mm max element size
fprintf('Mesh generated: %d nodes\n', size(model.Mesh.Nodes, 2));

%% Solve
fprintf('Solving PDE...\n');
tic;
result = solve(model);
solve_time = toc;
fprintf('Solved in %.2f seconds\n', solve_time);

%% Extract results
temps = result.Temperature;
max_tempC = max(temps);
min_tempC = min(temps);
mean_tempC = mean(temps);

fprintf('Temperature results:\n');
fprintf('  Max:  %.2f °C\n', max_tempC);
fprintf('  Min:  %.2f °C\n', min_tempC);
fprintf('  Mean: %.2f °C\n', mean_tempC);

%% Compute mass
% Approximate volume from mesh
mesh_volume = 0;
if model.Geometry.NumCells > 0
    % For 3D meshes, compute volume from elements
    nodes = model.Mesh.Nodes;
    elements = model.Mesh.Elements;
    
    % Simple bounding box volume (rough approximation)
    bbox = model.Geometry.BoundingBox;
    approx_volume_m3 = prod(bbox(:,2) - bbox(:,1));
    
    % Convert to mm³ then to mass
    volume_mm3 = approx_volume_m3 * 1e9;
    mass_kg = rho * approx_volume_m3;
    mass_g = mass_kg * 1000;
else
    mass_g = 0;
end

fprintf('Estimated mass: %.2f g\n', mass_g);

%% Save plots
try
    % Temperature distribution plot
    figure('Visible', 'off');
    pdeplot3D(model, 'ColorMapData', result.Temperature);
    title(sprintf('Temperature Distribution (Max: %.1f°C)', max_tempC));
    colorbar;
    saveas(gcf, fullfile(plots_dir, 'temperature_distribution.png'));
    close(gcf);
    
    % Mesh plot
    figure('Visible', 'off');
    pdemesh(model);
    title('Mesh');
    saveas(gcf, fullfile(plots_dir, 'mesh.png'));
    close(gcf);
    
    fprintf('Plots saved to %s\n', plots_dir);
catch ME
    fprintf('Warning: Could not save plots: %s\n', ME.message);
end

%% Save results to JSON
result_struct = struct(...
    'max_tempC', max_tempC, ...
    'min_tempC', min_tempC, ...
    'mean_tempC', mean_tempC, ...
    'mass_g', mass_g, ...
    'solve_time_s', solve_time, ...
    'mesh_nodes', size(model.Mesh.Nodes, 2), ...
    'solver_status', 'success' ...
);

result_json = jsonencode(result_struct);
result_file = fullfile(output_dir, 'result.json');

fid = fopen(result_file, 'w');
fprintf(fid, '%s', result_json);
fclose(fid);

fprintf('Results saved to %s\n', result_file);
fprintf('Simulation complete!\n');

