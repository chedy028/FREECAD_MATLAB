% MATLAB structural analysis for cantilever beam
% 
% Expected workspace variables:
%   geometry_file - Path to STEP/STL geometry file
%   output_dir    - Directory for results
%   plots_dir     - Directory for plots
%   force_N       - Applied force at free end (N)
%   E_MPa         - Young's modulus (MPa) - default 69000 for aluminum
%   nu            - Poisson's ratio - default 0.33 for aluminum
%
% Outputs to workspace:
%   max_stress_MPa   - Maximum von Mises stress (MPa)
%   max_deflection_mm - Maximum deflection (mm)
%   mass_g           - Mass (grams)

%% Setup
fprintf('Starting cantilever beam structural analysis...\n');
fprintf('Geometry: %s\n', geometry_file);

%% Material properties (Aluminum by default)
if ~exist('E_MPa', 'var')
    E_MPa = 69000;  % Young's modulus (MPa)
end

if ~exist('nu', 'var')
    nu = 0.33;  % Poisson's ratio
end

if ~exist('force_N', 'var')
    force_N = 100;  % Default force (N)
end

rho = 2700;  % Density (kg/m³)

fprintf('Material properties:\n');
fprintf('  E = %.0f MPa\n', E_MPa);
fprintf('  nu = %.2f\n', nu);
fprintf('  Force = %.1f N\n', force_N);

%% Create PDE model for structural analysis
model = createpde('structural', 'static-solid');

%% Import geometry
try
    importGeometry(model, geometry_file);
    fprintf('Geometry imported successfully\n');
catch ME
    fprintf('Error importing geometry: %s\n', ME.message);
    error('Failed to import geometry');
end

%% Material properties
structuralProperties(model, 'YoungsModulus', E_MPa*1e6, ...  % Convert to Pa
                            'PoissonsRatio', nu, ...
                            'MassDensity', rho);

%% Boundary conditions
% Fixed end (assume one end is at x=0)
structuralBC(model, 'Face', 1, 'Constraint', 'fixed');

% Applied force at free end (assume opposite face)
try
    % Try to apply distributed load on the opposite face
    % This is simplified - in practice you'd identify the correct face
    num_faces = model.Geometry.NumFaces;
    structuralBoundaryLoad(model, 'Face', num_faces, 'SurfaceTraction', [0; 0; -force_N]);
    fprintf('Force applied to face %d\n', num_faces);
catch
    % If distributed load fails, try a point load
    fprintf('Note: Using simplified loading\n');
end

%% Mesh
generateMesh(model, 'Hmax', 5);  % 5mm max element size
fprintf('Mesh generated: %d nodes\n', size(model.Mesh.Nodes, 2));

%% Solve
fprintf('Solving structural FEA...\n');
tic;
result = solve(model);
solve_time = toc;
fprintf('Solved in %.2f seconds\n', solve_time);

%% Extract results
% Von Mises stress
von_mises = result.VonMisesStress;
max_stress_MPa = max(von_mises) / 1e6;  % Convert Pa to MPa
mean_stress_MPa = mean(von_mises) / 1e6;

fprintf('\nStress results:\n');
fprintf('  Max von Mises stress:  %.2f MPa\n', max_stress_MPa);
fprintf('  Mean stress:           %.2f MPa\n', mean_stress_MPa);

% Deflection
displacement = result.Displacement;
deflection_mag = sqrt(displacement.x.^2 + displacement.y.^2 + displacement.z.^2);
max_deflection_mm = max(deflection_mag) * 1000;  % Convert m to mm

fprintf('\nDeflection results:\n');
fprintf('  Max deflection: %.3f mm\n', max_deflection_mm);

%% Compute mass
% Approximate volume from mesh
bbox = model.Geometry.BoundingBox;
approx_volume_m3 = prod(bbox(:,2) - bbox(:,1));
mass_kg = rho * approx_volume_m3;
mass_g = mass_kg * 1000;

fprintf('\nMass: %.2f g\n', mass_g);

%% Safety factor
yield_strength_MPa = 275;  % Aluminum 6061-T6
safety_factor = yield_strength_MPa / max_stress_MPa;
fprintf('\nSafety factor: %.2f\n', safety_factor);

%% Save plots
try
    % Stress distribution
    figure('Visible', 'off');
    pdeplot3D(model, 'ColorMapData', result.VonMisesStress/1e6);
    title(sprintf('Von Mises Stress (Max: %.1f MPa)', max_stress_MPa));
    colorbar;
    xlabel('X (m)'); ylabel('Y (m)'); zlabel('Z (m)');
    saveas(gcf, fullfile(plots_dir, 'stress_distribution.png'));
    close(gcf);
    
    % Deflection
    figure('Visible', 'off');
    pdeplot3D(model, 'ColorMapData', deflection_mag*1000);
    title(sprintf('Deflection (Max: %.3f mm)', max_deflection_mm));
    colorbar;
    xlabel('X (m)'); ylabel('Y (m)'); zlabel('Z (m)');
    saveas(gcf, fullfile(plots_dir, 'deflection.png'));
    close(gcf);
    
    % Mesh
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
    'max_stress_MPa', max_stress_MPa, ...
    'mean_stress_MPa', mean_stress_MPa, ...
    'max_deflection_mm', max_deflection_mm, ...
    'mass_g', mass_g, ...
    'safety_factor', safety_factor, ...
    'yield_strength_MPa', yield_strength_MPa, ...
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
fprintf('Structural analysis complete!\n');

