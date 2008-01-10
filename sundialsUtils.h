#pragma once

#include <nvector/nvector_serial.h>
#include <sundials/sundials_dense.h>
#include <sundials/sundials_types.h>

#include <cvode/cvode.h>
#include <cvode/cvode_dense.h>
#include <ida/ida.h>
#include <ida/ida_dense.h>

#include <iostream>
#include <vector>

// wrapper class for Sundials "N_Vector"
class sdVector {
public:
	sdVector(unsigned int n);
	sdVector(N_Vector other);
	sdVector(const sdVector& other);
	~sdVector(void);
	realtype& operator()(unsigned int i);
	realtype operator()(unsigned int i) const;
	N_Vector forSundials(void) const {return v;}
	unsigned int length(void) const {return n;}
private:
	N_Vector v;
	bool alloc;
	unsigned int n;
};

std::ostream& operator<<(std::ostream& os, const sdVector& v);

// wrapper class for Sundials DenseMat
class sdMatrix 
{
public:
	sdMatrix(unsigned int n, unsigned int m);
	sdMatrix(DenseMat other);
	~sdMatrix(void);
	realtype& operator()(unsigned int i, unsigned int j);
	realtype operator()(unsigned int i, unsigned int j) const;
	DenseMat forSundials(void) const {return M;}
private:
	DenseMat M;
	bool alloc;
};

class sdODE {
public:
	virtual int f(realtype t, sdVector& y, sdVector& ydot)=0;
	virtual int g(realtype t, sdVector& y, realtype* gOut) {return 0;}
	virtual int Jac(realtype t, sdVector& y, sdVector& fy, sdMatrix& J)=0;
	virtual ~sdODE(void) {}
};

// wrapper class for the Sundials CVODE solver
class sundialsCVODE
{
public:
	sundialsCVODE(unsigned int n);
	~sundialsCVODE(void);

	void initialize(void);
	int integrateToTime(realtype t);
	void setODE(sdODE* newODE);
	int getRootInfo(); 
	void printStats();
	
	// Check function return value...
	//   opt == 0 means SUNDIALS function allocates memory so check if
	//            returned NULL pointer
	//   opt == 1 means SUNDIALS function returns a flag so check if
	//            flag >= 0
	//   opt == 2 means function allocates memory so check if returned
	//            NULL pointer 
	static int check_flag(void *flagvalue, char *funcname, int opt);
	
	realtype reltol;
	sdVector abstol;
	
	int linearMultistepMethod; // CV_ADAMS for non-stiff problems, CV_BDF for stiff problems
	int nonlinearSolverMethod; // CV_FUNCTIONAL for non-stiff problems, CV_NEWTON for stiff problems
	bool findRoots; // Specify whether or not to use the function g for rootfinding
	
	realtype t0; // initial time
	realtype tInt; // time reached by integrator
	sdVector y0;
	sdVector y;
	std::vector<int> rootsFound;
	unsigned int nRoots;
private:

	static int f(realtype t, N_Vector yIn, N_Vector ydotIn, void *f_data);
	static int g(realtype t, N_Vector yIn, realtype *gout, void *g_data);
	static int Jac(long int N, DenseMat Jin, realtype t,
	               N_Vector yIn, N_Vector fy, void *jac_data,
	               N_Vector tmp1, N_Vector tmp2, N_Vector tmp3);
	
	sdODE* theODE;
	void *sundialsMem;
	int flag;
	int flagr;
	int nEq;
};


class sdDAE {
public:
	virtual int f(realtype t, sdVector& y, sdVector& ydot, sdVector& res)=0;
	virtual int g(realtype t, sdVector& y, sdVector& ydot, realtype* gOut) {return 0;}
	virtual int Jac(realtype t, sdVector& y, sdVector& ydot, sdVector& res,
		            realtype c_j, sdMatrix& J)=0;
	virtual ~sdDAE(void) {}
};


// wrapper class for the Sundials IDA solver
// for Differential-Algebraic Equations
class sundialsIDA
{
public:
	sundialsIDA(unsigned int n);
	~sundialsIDA(void);

	void initialize(void);
	int integrateToTime(realtype t);
	void setDAE(sdDAE* newDAE);
	int getRootInfo(); 
	void printStats();
	
	// Check function return value...
	//   opt == 0 means SUNDIALS function allocates memory so check if
	//            returned NULL pointer
	//   opt == 1 means SUNDIALS function returns a flag so check if
	//            flag >= 0
	//   opt == 2 means function allocates memory so check if returned
	//            NULL pointer 
	static int check_flag(void *flagvalue, char *funcname, int opt);
	
	realtype reltol;
	sdVector abstol;
	
	bool findRoots; // Specify whether or not to use the function g for rootfinding
	
	realtype t0; // initial time
	realtype tInt; // time reached by integrator
	sdVector y0; // initial condition
	sdVector ydot0;
	sdVector y;
	sdVector ydot;
	sdVector componentId; // elements are 1.0 for differential variables, 0.0 for algebraic
	std::vector<int> rootsFound;
	unsigned int nRoots;
private:

	static int f(realtype t, N_Vector yIn, N_Vector ydotIn, N_Vector resIn, void *f_data); // f(y) = res
	static int g(realtype t, N_Vector yIn, N_Vector ydotIn, realtype *gout, void *g_data);
	static int Jac(long int N, realtype t, N_Vector yIn, N_Vector ydotIn, 
		           N_Vector res, realtype c_j, void *jac_data, DenseMat Jin, 
				   N_Vector tmp1, N_Vector tmp2, N_Vector tmp3);
	
	sdDAE* theDAE;
	void *sundialsMem;
	int flag;
	int flagr;
	int nEq;
};


