code_kalman_ar1 = """

data {
    int N; // number of time steps
    int nreg; // number of regressors
    vector[N] d; // n-composites vectors of N-time-steps -- the data
    vector[N] s; // corresponding std deviation for each data point
    vector[nreg] regressors[N]; // nreg regressors of N-time-steps
    real<lower=0> sigma_trend_prior;
    real<lower=0> sigma_seas_prior;
    real<lower=0> sigma_AR_prior;
    real<lower=0> S;
    
}

transformed data {

    // Set value of nx
    int nx = nreg+7;
    
    // Declare F-vector (observation projection vector)
    vector[nx] F[N+1];
    
    // Initialize
    for(t in 1:N+1){
        F[t] = rep_vector(0, nx);
    }
    
    // First time point
    F[1][1] = 1;
    F[1][2] = 0;
    F[1][3] = 1;
    F[1][4] = 0;
    F[1][5] = 1;
    F[1][6] = 0;
    for(i in 1:nreg){
        F[1][6+i] = 0; 
    }  
    F[1][6+nreg+1] = 1;
    
    // Loop over next time points
    for(t in 2:N+1){
        F[t][1] = 1;
        F[t][2] = 0;
        F[t][3] = 1;
        F[t][4] = 0;
        F[t][5] = 1;
        F[t][6] = 0;
        for(i in 1:nreg){
            F[t][6+i] = regressors[t-1][i]; 
        }  
        F[t][6+nreg+1] = 1;
    }
}

parameters {
    real<lower=0> sigma_trend;
    real<lower=0> sigma_seas;
    real<lower=0> sigma_AR;
    real<lower=0, upper=1> rhoAR;
}

transformed parameters{

    // Declare intermediate Kalman objects
    vector[nx] x_hat[N+1];
    vector[nx] x_bar[N+1];
    matrix[nx,nx] C_hat[N+1];
    vector[N+1] C_y;
    vector[nx] K[N+1];
    matrix[nx,nx] C_bar[N+1];
    vector[N+1] v;

    // Declare state-space model matrices
    matrix[nx, nx] G; // G-matrix (state transition matrix)
    matrix[nx, nx] W; // W-matrix (state covariance)
    matrix[nx, nx] C; // C-matrix (observation covariance)
    
    // Initialize state-space matrices
    G = rep_matrix(0, nx, nx);
    W = rep_matrix(0, nx, nx);
    C = rep_matrix(0, nx, nx);
    
    // Initialize Kalman filter stuff
    C_y = rep_vector(0, N+1);
    v = rep_vector(0, N+1);
    for(t in 1:N+1){
        x_hat[t] = rep_vector(0, nx);
        x_bar[t] = rep_vector(0, nx);
        K[t] = rep_vector(0, nx);
        C_bar[t] = rep_matrix(0, nx, nx);
        C_hat[t] = rep_matrix(0, nx, nx);
    }
    
    // Assign the G matrix
    
    // Trend part
    G[1,1] = 1;
    G[1,2] = 1;
    G[2,1] = 0;
    G[2,2] = 1;
    
    // 12-month seasonal part
    G[3,3] = cos(2*pi()/12);
    G[3,4] = sin(2*pi()/12);
    G[4,3] = -sin(2*pi()/12);
    G[4,4] = cos(2*pi()/12);
    
    // 6-month seasonal part
    G[5,5] = cos(2*pi()/6);
    G[5,6] = sin(2*pi()/6);
    G[6,5] = -sin(2*pi()/6);
    G[6,6] = cos(2*pi()/6);
    
    // Regressor part
    for(i in 1:nreg){
        G[6+i,6+i] = 1;
    }
    
    // AR process part
    G[6+nreg+1,6+nreg+1] = rhoAR;
    
    // Assign W matrix
    W[1,1] = 1e-10;
    W[2,2] = sigma_trend^2;
    W[3,3] = sigma_seas^2;
    W[4,4] = sigma_seas^2;
    W[5,5] = sigma_seas^2;
    W[6,6] = sigma_seas^2;
    for(i in 1:nreg){
        W[6+i,6+i] = 1e-10;
    }
    W[nx,nx] = sigma_AR^2;
    
    // Assign C matrix
    
    // Prior covariance of regression coefficients (and seasonal cycle and trend amplitudes)
    for(i in 1:(nx-1)){
        C[i,i] = S;
    }
    
    // Prior (stationary) covariance of the AR1 process
    C[nx,nx] = sigma_AR^2/(1-rhoAR^2);
    
    // Kalman filtering
    
    // Initialize C_bar
    C_bar[1] = C;
        
    // Do the forward filtering
    for(t in 2:N+1){
        x_hat[t] = G*x_bar[t-1];
        C_hat[t] = G*(C_bar[t-1]*G') + W;
        C_y[t] = F[t]'*C_hat[t]*F[t] + s[t-1]^2;
        K[t] = (C_hat[t]*F[t])/C_y[t];
        v[t] = d[t-1] - F[t]'*x_hat[t];
        x_bar[t] = x_hat[t] + K[t]*v[t];
        C_bar[t] = C_hat[t] - (K[t]*F[t]')*C_hat[t];
    }
}

model {
 
    // Priors on hyper parameters
    sigma_trend ~ normal(0, sigma_trend_prior);
    sigma_seas ~ normal(0, sigma_seas_prior);
    sigma_AR ~ normal(0, sigma_AR_prior);
    rhoAR ~ uniform(0, 1);
    
    // Construct target density
    for(t in 2:N+1){
        target += normal_lpdf(v[t] | 0, sqrt(C_y[t]));
    } 
}

generated quantities {

    // Declare Kalman smoother quantities
    vector[N] trend;
    vector[N] slope;
    vector[N] seasonal;
    vector[N] ar;
    vector[nreg] beta;
    vector[N] residuals;
    vector[nx] x[N];
    vector[nx] x_realization[N+1];
    vector[nx] x_ubar[N+1];
    vector[nx] x_realization_hat[N+1];
    vector[N+1] y_realization;
    vector[N+1] v_realization;
    vector[nx] r[N+2];
    vector[nx] r_realization[N+2];
    matrix[nx,nx] L[N+2];
    matrix[nx,nx] M[N+2];
    matrix[nx,nx] C_twidle[N+1];
    vector[nx] x_twidle[N+1];
    vector[nx] x_realization_twidle[N+1];
    
    // Initialize matrix quantities and end points of Kalman smoothing vectors
    for(t in 1:N+1){
        L[t] = rep_matrix(0, nx, nx);
        M[t] = rep_matrix(0, nx, nx);
        C_twidle[t] = rep_matrix(0, nx, nx);
    }
    L[N+2] = rep_matrix(0, nx, nx);
    M[N+2] = rep_matrix(0, nx, nx);
    r[N+2] = rep_vector(0, nx);
    r_realization[N+2] = rep_vector(0, nx);
 
    // Generate a draw from the state-space equations
    x_realization[1] = multi_normal_rng(rep_vector(0, nx), C);
    y_realization[1] = F[1]'*x_realization[1] + normal_rng(0, 10*s[1]);
    for(t in 2:N+1){
        x_realization[t] = G*x_realization[t-1] + multi_normal_rng(rep_vector(0, nx), W);
        y_realization[t] = F[t]'*x_realization[t] + normal_rng(0, s[t-1]);
    }
    
    // Generate Kalman filter of realization; x_realization_hat
    x_ubar[1] = rep_vector(0, nx);
    for(t in 2:N+1){
        x_realization_hat[t] = G*x_ubar[t-1];
        v_realization[t] = y_realization[t] - F[t]'*x_realization_hat[t];
        x_ubar[t] = x_realization_hat[t] + K[t]*v_realization[t];
    }
    
    // Generate Kalman smoother of realization and of data
    for(t in 1:N+1){
    
        L[N+2-t] = G - G*(K[N+2-t]*F[N+2-t]');
        r[N+2-t] = F[N+2-t]*v[N+2-t]/C_y[N+2-t] + L[N+2-t]'*r[N+2-t+1];
        r_realization[N+2-t] = F[N+2-t]*v_realization[N+2-t]/C_y[N+2-t] + L[N+2-t]'*r_realization[N+2-t+1];
        M[N+2-t] = (F[N+2-t]*F[N+2-t]')/C_y[N+2-t] + L[N+2-t]'*(M[N+2-t+1]*L[N+2-t]);
        x_twidle[N+2-t] = x_hat[N+2-t] + C_hat[N+2-t]*r[N+2-t];
        x_realization_twidle[N+2-t] = x_realization_hat[N+2-t] + C_hat[N+2-t]*r_realization[N+2-t];
        C_twidle[N+2-t] = C_hat[N+2-t] - C_hat[N+2-t]*(M[N+2-t]*C_hat[N+2-t]);        
    }
    
    for(t in 1:N){
        x[t] = x_realization[t+1] - x_realization_twidle[t+1] + x_twidle[t+1];
        trend[t] = x[t][1];
        slope[t] = x[t][2];
        seasonal[t] = x[t][3] + x[t][5];
        ar[t] = x[t][nx];
        residuals[t] = d[t] - (F[t]'*x[t] - ar[t]);
    }
    for(i in 1:nreg){
        beta[i] = x[1][5+i];
    }
}

"""

code_kalman_ar2 = """

data {
    int N; // number of time steps
    int nreg; // number of regressors
    int nx; // length of state vector
    vector[N] d; // n-composites vectors of N-time-steps -- the data
    vector[N] s; // corresponding std deviation for each data point
    vector[nreg] regressors[N]; // nreg regressors of N-time-steps
    real<lower=0> sigma_trend_prior;
    real<lower=0> sigma_seas_prior;
    real<lower=0> sigma_AR_prior;
    real<lower=0> S;
}

transformed data {
    
    // Declare F-vector (observation projection vector)
    vector[nx] F[N+1];
    
    // Initialize
    for(t in 1:N+1){
        F[t] = rep_vector(0, nx);
    }
    
    // First time point
    F[1][1] = 1;
    F[1][2] = 0;
    F[1][3] = 1;
    F[1][4] = 0;
    F[1][5] = 1;
    F[1][6] = 0;
    for(i in 1:nreg){
        F[1][6+i] = 0; 
    }  
    F[1][6+nreg+1] = 1;
    
    // Loop over next time points
    for(t in 2:N+1){
        F[t][1] = 1;
        F[t][2] = 0;
        F[t][3] = 1;
        F[t][4] = 0;
        F[t][5] = 1;
        F[t][6] = 0;
        for(i in 1:nreg){
            F[t][6+i] = regressors[t-1][i]; 
        }  
        F[t][6+nreg+1] = 1;
    }
}

parameters {
    real<lower=0> sigma_trend;
    real<lower=0> sigma_seas;
    real<lower=0> sigma_AR;
    real<lower=0, upper=1> rhoAR1;
    real<lower=0, upper=1> rhoAR2;
}

transformed parameters{

    // Declare intermediate Kalman objects
    vector[nx] x_hat[N+1];
    vector[nx] x_bar[N+1];
    matrix[nx,nx] C_hat[N+1];
    vector[N+1] C_y;
    vector[nx] K[N+1];
    matrix[nx,nx] C_bar[N+1];
    vector[N+1] v;

    // Declare state-space model matrices
    matrix[nx, nx] G; // G-matrix (state transition matrix)
    matrix[nx, nx] W; // W-matrix (state covariance)
    matrix[nx, nx] C; // C-matrix (observation covariance)
    
    // Initialize state-space matrices
    G = rep_matrix(0, nx, nx);
    W = rep_matrix(0, nx, nx);
    C = rep_matrix(0, nx, nx);
    
    // Initialize Kalman filter stuff
    C_y = rep_vector(0, N+1);
    v = rep_vector(0, N+1);
    for(t in 1:N+1){
        x_hat[t] = rep_vector(0, nx);
        x_bar[t] = rep_vector(0, nx);
        K[t] = rep_vector(0, nx);
        C_bar[t] = rep_matrix(0, nx, nx);
        C_hat[t] = rep_matrix(0, nx, nx);
    }
    
    // Assign the G matrix
    
    // Trend part
    G[1,1] = 1;
    G[1,2] = 1;
    G[2,1] = 0;
    G[2,2] = 1;
    
    // 12-month seasonal part
    G[3,3] = cos(2*pi()/12);
    G[3,4] = sin(2*pi()/12);
    G[4,3] = -sin(2*pi()/12);
    G[4,4] = cos(2*pi()/12);
    
    // 6-month seasonal part
    G[5,5] = cos(2*pi()/6);
    G[5,6] = sin(2*pi()/6);
    G[6,5] = -sin(2*pi()/6);
    G[6,6] = cos(2*pi()/6);
    
    // Regressor part
    for(i in 1:nreg){
        G[6+i,6+i] = 1;
    }
    
    // AR process part
    G[6+nreg+1,6+nreg+1] = rhoAR1;
    G[6+nreg+1,6+nreg+2] = rhoAR2;
    G[6+nreg+2, 6+nreg+1] = 1;

    // Assign W matrix
    W[1,1] = 1e-10;
    W[2,2] = sigma_trend^2;
    W[3,3] = sigma_seas^2;
    W[4,4] = sigma_seas^2;
    W[5,5] = sigma_seas^2;
    W[6,6] = sigma_seas^2;
    for(i in 1:nreg){
        W[6+i,6+i] = 1e-10;
    }
    W[nx,nx] = sigma_AR^2;
    
    // Assign C matrix
    
    // Prior covariance of regression coefficients (and seasonal cycle and trend amplitudes)
    for(i in 1:(nx-1)){
        C[i,i] = S;
    }
    
    // Prior (stationary) covariance of the AR1 process
    C[nx, nx] = sigma_AR^2/(1-(rhoAR1^2 + rhoAR2^2) - 2*rhoAR2*rhoAR1^2);
    C[nx-1, nx-1] = sigma_AR^2/(1-(rhoAR1^2 + rhoAR2^2) - 2*rhoAR2*rhoAR1^2);
    C[nx, nx-1] = C[nx, nx]*rhoAR1/(1-rhoAR2);
    C[nx-1, nx] = C[nx, nx]*rhoAR1/(1-rhoAR2);

    // Kalman filtering
    
    // Initialize C_bar
    C_bar[1] = C;
        
    // Do the forward filtering
    for(t in 2:N+1){
        x_hat[t] = G*x_bar[t-1];
        C_hat[t] = G*(C_bar[t-1]*G') + W;
        C_y[t] = F[t]'*C_hat[t]*F[t] + s[t-1]^2;
        K[t] = (C_hat[t]*F[t])/C_y[t];
        v[t] = d[t-1] - F[t]'*x_hat[t];
        x_bar[t] = x_hat[t] + K[t]*v[t];
        C_bar[t] = C_hat[t] - (K[t]*F[t]')*C_hat[t];
    }
}

model {
 
    // Priors on hyper parameters
    sigma_trend ~ normal(0, sigma_trend_prior);
    sigma_seas ~ normal(0, sigma_seas_prior);
    sigma_AR ~ normal(0, sigma_AR_prior);
    rhoAR1 ~ uniform(0, 1);
    rhoAR2 ~ uniform(0, sqrt(rnoAR1^4+1-rhoAR1^2)-rhoAR1^2);

    // Construct target density
    for(t in 2:N+1){
        target += normal_lpdf(v[t] | 0, sqrt(C_y[t]));
    } 
}

generated quantities {

    // Declare Kalman smoother quantities
    vector[N] trend;
    vector[N] seasonal;
    vector[N] ar;
    vector[nx] x[N];
    vector[N] residuals;
    vector[nx] x_realization[N+1];
    vector[nx] x_ubar[N+1];
    vector[nx] x_realization_hat[N+1];
    vector[N+1] y_realization;
    vector[N+1] v_realization;
    vector[nx] r[N+2];
    vector[nx] r_realization[N+2];
    matrix[nx,nx] L[N+2];
    matrix[nx,nx] M[N+2];
    matrix[nx,nx] C_twidle[N+1];
    vector[nx] x_twidle[N+1];
    vector[nx] x_realization_twidle[N+1];
    
    // Initialize matrix quantities and end points of Kalman smoothing vectors
    for(t in 1:N+1){
        L[t] = rep_matrix(0, nx, nx);
        M[t] = rep_matrix(0, nx, nx);
        C_twidle[t] = rep_matrix(0, nx, nx);
    }
    L[N+2] = rep_matrix(0, nx, nx);
    M[N+2] = rep_matrix(0, nx, nx);
    r[N+2] = rep_vector(0, nx);
    r_realization[N+2] = rep_vector(0, nx);
 
    // Generate a draw from the state-space equations
    x_realization[1] = multi_normal_rng(rep_vector(0, nx), C);
    y_realization[1] = F[1]'*x_realization[1] + normal_rng(0, 10*s[1]);
    for(t in 2:N+1){
        x_realization[t] = G*x_realization[t-1] + multi_normal_rng(rep_vector(0, nx), W);
        y_realization[t] = F[t]'*x_realization[t] + normal_rng(0, s[t-1]);
    }
    
    // Generate Kalman filter of realization; x_realization_hat
    x_ubar[1] = rep_vector(0, nx);
    for(t in 2:N+1){
        x_realization_hat[t] = G*x_ubar[t-1];
        v_realization[t] = y_realization[t] - F[t]'*x_realization_hat[t];
        x_ubar[t] = x_realization_hat[t] + K[t]*v_realization[t];
    }
    
    // Generate Kalman smoother of realization and of data
    for(t in 1:N+1){
    
        L[N+2-t] = G - G*(K[N+2-t]*F[N+2-t]');
        r[N+2-t] = F[N+2-t]*v[N+2-t]/C_y[N+2-t] + L[N+2-t]'*r[N+2-t+1];
        r_realization[N+2-t] = F[N+2-t]*v_realization[N+2-t]/C_y[N+2-t] + L[N+2-t]'*r_realization[N+2-t+1];
        M[N+2-t] = (F[N+2-t]*F[N+2-t]')/C_y[N+2-t] + L[N+2-t]'*(M[N+2-t+1]*L[N+2-t]);
        x_twidle[N+2-t] = x_hat[N+2-t] + C_hat[N+2-t]*r[N+2-t];
        x_realization_twidle[N+2-t] = x_realization_hat[N+2-t] + C_hat[N+2-t]*r_realization[N+2-t];
        C_twidle[N+2-t] = C_hat[N+2-t] - C_hat[N+2-t]*(M[N+2-t]*C_hat[N+2-t]);        
    }
    
    for(t in 1:N){
        x[t] = x_realization[t+1] - x_realization_twidle[t+1] + x_twidle[t+1];
        trend[t] = x[t][1];
        seasonal[t] = x[t][3] + x[t][5];
        ar[t] = x[t][nx];
        residuals[t] = d[t] - (F[t]'*x[t] - ar[t]);
    }
}

"""
